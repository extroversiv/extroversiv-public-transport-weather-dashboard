import os
from datetime import datetime
import pytz
import dash_bootstrap_components as dbc
from dash import Dash, html, dcc, Input, Output, State, clientside_callback

from src.ApiKeys import ApiKeys
from src.transport.Hafas import Hafas
from src.weather.DWD import DWD

# os.environ['TZ'] = 'Europe/Berlin'
api_keys = ApiKeys('config/api_keys.json')

# refresh rates
CLOCK_REFRESH = 60 * 1000
TRANSPORT_REFRESH = 60 * 1000
WEATHER_REFRESH = 60 * 60 * 1000

# set up dash and other global objects
# https://hellodash.pythonanywhere.com/
dbc_css = "assets/dbc.css"
app = Dash(__name__, external_stylesheets=[dbc.themes.YETI, dbc_css])
transport = Hafas()
weather = DWD(api_keys)

# set up dash app layout
app.layout = dbc.Container(fluid=True, className="dbc", children=[
    dbc.Row(children=[
        dbc.Col([
            html.Div(id='clock'),
            dcc.Interval(id='clock_refresh', n_intervals=0,
                         interval=CLOCK_REFRESH),
        ], width=1),
        dbc.Col(html.H2('🚉 Öffis 💚', style={'text-align': 'center'}), width=4),
        dbc.Col(width=2),
        dbc.Col(html.H2('☔ Wetter ⛅', style={'text-align': 'center'}),
                width=4),
        dbc.Col(html.Span(
            [
                dbc.Label('☽', html_for="switch"),
                dbc.Switch(id="switch", value=True,
                           className="d-inline-block ms-1", persistence=True),
                dbc.Label('☼', html_for="switch"),
            ]
        ), width=1, align='center', style={'text-align': 'right'})
    ], align='center', justify='evenly'
    ),
    dbc.Row(children=[
        dbc.Col(width=7, children=[
            dbc.Row([
                dbc.Col(width=8, children=dcc.Dropdown(
                    id='transport_locations',
                    multi=True,
                    search_value='Berlin',
                    placeholder='Haltestellen',
                    persistence=True)
                        ),
                dbc.Col(width=2, children=dbc.InputGroup(
                    [dbc.InputGroupText('trips:'),
                     dbc.Input(id='n_rows', value=15,
                               placeholder='number of trips',
                               type='number', min=1,
                               step=1,
                               persistence=True)])
                        ),
                dbc.Col(width=2, children=dbc.InputGroup(
                    [dbc.InputGroupText('offset:'),
                     dbc.Input(id='timedelta', value=5,
                               placeholder='timedelta in minutes',
                               type='number', min=0,
                               step=1,
                               persistence=True)])
                        ),
            ]),
            dbc.Row(id='transport_data'),
            dcc.Interval(id='transport_refresh', n_intervals=0,
                         interval=TRANSPORT_REFRESH),
        ]),
        dbc.Col(width=5, children=[
            dbc.Row(dcc.Dropdown(id='weather_locations', multi=True,
                                 search_value='Berlin',
                                 placeholder='Wetterstationen',
                                 persistence=True)),
            dbc.Row(id='weather_data'),
            dcc.Interval(id='weather_refresh', n_intervals=0,
                         interval=WEATHER_REFRESH),
        ])
    ])
])

clientside_callback(
    """ 
    (switchOn) => {
       switchOn
         ? document.documentElement.setAttribute('data-bs-theme', 'light')
         : document.documentElement.setAttribute('data-bs-theme', 'dark')
       return window.dash_clientside.no_update
    }
    """,
    Output("switch", "id"),
    Input("switch", "value"),
)


@app.callback(
    Output('clock', 'children'),
    Input('clock_refresh', 'n_intervals')
)
def update_clock(_):
    return datetime.now().strftime('%H:%M') + ' Uhr'


# public transport callbacks
@app.callback(
    Output('transport_locations', 'options'),
    [Input('transport_locations', 'search_value')],
    [State('transport_locations', 'value')]
)
def find_transport_locations(search, selected, max_new_locations=5):
    new_station_names = transport.find_locations(search, max_new_locations)
    if selected:
        return selected + new_station_names
    else:
        return new_station_names


@app.callback(
    Output('transport_data', 'children'),
    [Input('transport_locations', 'value'),
     Input('n_rows', 'value'),
     Input('timedelta', 'value'),
     Input("switch", "value"),
     Input('transport_refresh', 'n_intervals')]
)
def get_transport_data(locations, n_rows, timedelta, light_mode, _):
    if locations:
        transport.update_locations(locations)
        tables = []
        for name in locations:
            print(f'updating transport data for {name} ...')
            # workaround right now, should have a checkbox
            # for products here for each station
            if '(S)' in name:
                products = ['S']
            elif '(U)' in name:
                products = ['U']
            elif '(S+U)' in name:
                products = ['S', 'U']
            else:
                products = transport.products.keys()

            df = transport.get_data(name=name, products=products,
                                    n_rows=int(n_rows), timedelta=timedelta)
            table = transport.data_to_table(df, name, light_mode=light_mode)

            # add to dashboard
            tables.append(table)

        # make it two columns
        if len(tables) > 0:
            cols = 2
            width = 12 // cols
            dbc_grid = chunks(tables, cols)
            column = dbc.Row(
                [dbc.Col(dbc_grid[c], width=width) for c in range(cols)])
        else:
            column = html.Div()

        return column
    else:
        return


# def get_products(name: str) -> list:
#     # checklist of types of transportation
#     checklist = dbc.Checklist(id='products {name}',
#                               options=list(transport.products.keys()),
#                               value=['S', 'U', 'Bus', 'Tram'],
#                               inline=True,
#                               persistence=True,
#                               )
#     return checklist.value


# weather callbacks
@app.callback(
    Output('weather_locations', 'options'),
    [Input('weather_locations', 'search_value')],
    [State('weather_locations', 'value')]
)
def find_weather_locations(search, selected, max_new_locations=5):
    new_station_names = weather.find_locations(search, max_new_locations)
    if selected:
        return selected + new_station_names
    else:
        return new_station_names


@app.callback(
    Output('weather_data', 'children'),
    [Input('weather_locations', 'value'),
     Input("switch", "value"),
     Input('weather_refresh', 'n_intervals')]
)
def get_weather_data(locations, switch, _):
    if locations:
        weather.update_locations(locations)
        print(f'updating weather data for {locations} ...')
        df = weather.get_data(locations)
        graph = weather.data_to_graph(df, name='weather', light_mode=switch)
        return graph
    else:
        return


def chunks(data: list, columns: int) -> list:
    # split 1-D array in a certain number of 2-D array
    data_out = []
    for n in range(columns):
        data_out.append([])
    for i, t in enumerate(data):
        data_out[i % columns].append(t)
    return data_out


if __name__ == '__main__':
    app.run_server(debug=False, host='0.0.0.0', port=8050)
