from datetime import datetime

import numpy as np
import pandas as pd
from dash import dash_table, html
from pyhafas.client import HafasClient
from pyhafas.profile import DBProfile

from src.LocationData import LocationData
from src.utils import convert_tz


class Hafas(LocationData):
    def __init__(self):
        super().__init__()
        self.client = HafasClient(profile=DBProfile())
        # products for this profile are DBProfile.availableProducts
        self.products = {
            'Bahn': ['long_distance_express', 'long_distance',
                     'regional_express', 'regional'],
            'S': ['suburban'],
            'U': ['subway'],
            'Bus': ['bus'],
            'Tram': ['tram'],
            '...': ['ferry', 'taxi']
        }
        self._station_direction_dict = dict()

    def find_locations(self, name, number):
        new_locations = self.client.locations(name)
        if new_locations is None:
            return []

        # try to find the exact match first
        # (this is not always the first element)
        for idx, location in enumerate(new_locations):
            if location.name == name:
                # swap items in list
                tmp = new_locations[0]
                new_locations[0] = location
                new_locations[idx] = tmp

        new_locations_dict = {s.name: s for s in
                              new_locations[:min(number, len(new_locations))]}
        self._locations.update(new_locations_dict)
        return list(new_locations_dict.keys())

    def get_data(self, name: str, products: list,
                 n_rows: int = 5, timedelta: int = 5,
                 max_duration: int = 120) -> pd.DataFrame:
        station = self._locations[name]

        # get departures from hafas client
        products_real = {k: False for k, _ in
                         DBProfile.availableProducts.items()}
        for value in products:
            for p in self.products[value]:
                products_real[p] = True

        departures = self.client.departures(
            station=station,
            date=datetime.now() + pd.Timedelta(timedelta, 'minutes'),
            duration=max_duration,
            max_trips=-1,
            products=products_real
        )

        # make pandas dataframe
        df = []
        for dep in departures:
            data = [dep.station.id,
                    dep.id,
                    dep.cancelled,
                    dep.dateTime,
                    dep.delay,
                    dep.direction,
                    dep.name,
                    dep.platform]
            df.append(data)
        df = pd.DataFrame(
            data=df,
            columns=['station_id', 'trip_id', 'cancelled', 'dateTime', 'delay',
                     'direction', 'name', 'platform']
        )

        # filter cancelled trips
        df = df[~(df['cancelled'])].copy()

        # add directions by checking the next stop
        df = self.add_directions(df)

        # stuff related to times
        df = convert_tz(df)
        df['dateTime'] = pd.to_datetime(df['dateTime'])
        df['delay'] = pd.to_timedelta(df['delay'])
        df['delay'] = df['delay'].fillna(pd.Timedelta(0))
        df['actualDepartTime'] = df['dateTime'] + df['delay']

        def foo(g, n_trips):
            f = g.sort_values(by='actualDepartTime', ascending=True)
            f = f if len(f) <= n_trips else f.iloc[:n_trips, :]
            return f

        # sort
        # df = df.sort_values(by='actualDepartTime', ascending=True)
        n_trips = int(np.ceil(n_rows / df['platform_direction'].nunique()))
        df = df.groupby('platform_direction').apply(foo, n_trips)
        df = df.reset_index(drop=True)

        return df

    def add_directions(self, df: pd.DataFrame) -> pd.DataFrame:
        # find and sort by direction, get trip details only once
        next_stop_id_list = []
        cols = ['trip_id', 'name', 'direction', 'station_id', 'platform']
        for idx, row in df[cols].iterrows():
            station_id = row['station_id']
            trip_id = row['trip_id']
            platform = row['platform']

            if platform:
                next_stop_id_list.append(str(platform))
            else:
                # store information for later
                if station_id not in self._station_direction_dict:
                    self._station_direction_dict.update({station_id: dict()})

                name_direction = f"{row['name']}_{row['direction']}"
                if name_direction in self._station_direction_dict[station_id]:
                    next_stop_id = self._station_direction_dict[station_id][
                        name_direction]
                else:
                    # get each trips info
                    trip_info = self.client.trip(trip_id)
                    # find current stop in list and get next stop
                    stopovers = trip_info.stopovers
                    stop_idx = [idx for idx in range(len(stopovers)) if
                                stopovers[idx].stop.id == station_id]
                    if len(stop_idx) == 1:
                        stop_idx = stop_idx[0]
                        if len(stopovers) > stop_idx:
                            next_stop_id = stopovers[stop_idx + 1].stop.id
                        else:
                            # Endhaltestelle or other error in finding
                            # this station in the trip
                            next_stop_id = '-1'
                    else:
                        # not found or disambigius
                        next_stop_id = '-1'
                    self._station_direction_dict[station_id].update(
                        {name_direction: next_stop_id})

                next_stop_id_list.append(str(next_stop_id))

        df['platform_direction'] = next_stop_id_list
        return df

    def data_to_table(self, df: pd.DataFrame, name: str,
                      light_mode=True) -> dash_table.DataTable:
        # format departure times with delays
        df['delay'] = round(df['delay'].dt.total_seconds() / 60).astype(int)
        time_string = df['dateTime'].dt.strftime('%H:%M')
        delay_string = df['delay'].apply(
            lambda u: '({:+d})'.format(u))  # :+d adds sign of u to string of u
        delay_string[df['delay'] == 0] = ''  # leave empty if there is no delay
        df['Abfahrt'] = time_string + ' ' + delay_string
        df['Bahnsteig'] = df['platform'].str.strip().values
        df['Linie'] = df['name'].str.strip().values
        df['Richtung'] = df['direction'].str.strip().values

        # stripes for different directions
        stripes = 'platform_direction'
        if stripes is not None and df[stripes].nunique() > 1:
            stripes_rows = [i for i in list(df.index) if
                            df.loc[i, stripes] in df[stripes].unique()[::2]]
        else:
            stripes_rows = []

        # create table
        df = df.reset_index(drop=True)
        show_columns = ['Abfahrt', 'Linie', 'Richtung']

        stripes_color = \
            'rgb(220, 220, 220)' if light_mode else 'rgb(70, 70, 70)'
        table = dash_table.DataTable(
            data=df.to_dict('records'),
            id=name,
            columns=[{"name": c, "id": c} for c in show_columns],
            style_data={
                'whiteSpace': 'nowrap',
                'height': 'auto'
            },
            style_data_conditional=[
                {
                    'if': {
                        'column_id': 'Richtung'
                    },
                    'whiteSpace': 'normal'
                },
                {
                    'if': {
                        'column_id': 'Abfahrt'
                    },
                    'textAlign': 'left',
                },
                {
                    'if': {
                        'filter_query': '{Abfahrt} contains "+"',
                        'column_id': 'Abfahrt'
                    },
                    'color': 'red',
                },
                {
                    'if': {
                        'filter_query': '{Abfahrt} contains "-"',
                        'column_id': 'Abfahrt'
                    },
                    'color': 'green',
                },
                {
                    'if': {'row_index': stripes_rows},
                    'backgroundColor': stripes_color
                }
            ]
        )

        name_short = name.split(',')[0]  # only the first part of the name
        table = html.Div([
            html.Div(name_short),
            table
        ])
        return table
