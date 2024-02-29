from datetime import date, timedelta

import pandas as pd
import plotly.express as px
from dash import dcc
from geopy.geocoders import HereV7, Nominatim
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest, DwdMosmixType
from wetterdienst.settings import Settings

from src.LocationData import LocationData
from src.utils import convert_tz


class DWD(LocationData):
    def __init__(self, api_keys):
        super().__init__()
        # I don't know whether this needs to be initialized at
        # every request or it's enough to do this once here
        self.DwdParameter = [
            'temperature_air_mean_200', 'wind_speed',
            'sunshine_duration',
            'precipitation_height_significant_weather_last_1h',
            'humidity'
        ]
        self.DwdSettings = Settings(ts_humanize=True, ts_si_units=True,
                                    ts_skip_empty=True)

        # geocoding engine
        if api_keys.here != '':
            self.geo = HereV7(apikey=api_keys.here)
        else:
            print("falling back to Nominatim API for "
                  "geocoding (this might fail due to rate limit)")
            self.geo = Nominatim(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0)'
                           ' Gecko/20100101 Firefox/66.0')

    def find_locations(self, name, number):
        if name:
            # get lon, lat of location
            new_locations = self.geo.geocode(name, exactly_one=False,
                                             limit=number)
            if new_locations is None:
                return []
            new_locations_dict = {s[0]: s[1] for s in
                                  new_locations}  # name: (lat, lon)
            self._locations.update(new_locations_dict)
            return list(new_locations_dict.keys())
        else:
            return []

    def get_data(self, name: str) -> pd.DataFrame:

        # parameter in ['cloud_cover_above_7_km', 'cloud_cover_below_1000_ft',
        #  'cloud_cover_below_500_ft', 'cloud_cover_between_2_to_7_km',
        #  'cloud_cover_effective', 'cloud_cover_total',
        #  'precipitation_height_significant_weather_last_1h',
        #  'precipitation_height_significant_weather_last_3h',
        #  'pressure_air_site_reduced', 'probability_fog_last_12h',
        #  'probability_fog_last_1h', 'probability_fog_last_6h',
        #  'probability_precipitation_height_gt_0_0_mm_last_12h',
        #  'probability_precipitation_height_gt_0_2_mm_last_12h',
        #  'probability_precipitation_height_gt_0_2_mm_last_24h',
        #  'probability_precipitation_height_gt_0_2_mm_last_6h',
        #  'probability_precipitation_height_gt_1_0_mm_last_12h',
        #  'probability_precipitation_height_gt_5_0_mm_last_12h',
        #  'probability_precipitation_height_gt_5_0_mm_last_24h',
        #  'probability_precipitation_height_gt_5_0_mm_last_6h',
        #  'probability_wind_gust_ge_25_kn_last_12h',
        #  'probability_wind_gust_ge_40_kn_last_12h',
        #  'probability_wind_gust_ge_55_kn_last_12h', 'radiation_global',
        #  'sunshine_duration', 'temperature_air_max_200',
        #  'temperature_air_mean_005', 'temperature_air_mean_200',
        #  'temperature_air_min_200', 'temperature_dew_point_mean_200',
        #  'visibility_range', 'water_equivalent_snow_depth_new_last_1h',
        #  'water_equivalent_snow_depth_new_last_3h', 'weather_last_6h',
        #  'weather_significant', 'wind_direction', 'wind_gust_max_last_12h',
        #  'wind_gust_max_last_1h', 'wind_gust_max_last_3h', 'wind_speed']

        # forecast service
        dwd_request = DwdMosmixRequest(
            # parameter='small',
            parameter=self.DwdParameter,
            mosmix_type=DwdMosmixType.SMALL,
            # large is only released very 6 hours (3, 9, 15, 21)
            settings=self.DwdSettings,
        )

        # get the weather stations near lon, lat of the locations
        nearest_stations = {}
        for n in name:
            latlon = self._locations[n]
            nearby_stations = dwd_request.filter_by_distance(
                latlon,
                distance=50,
                unit='km').df.to_pandas()
            # already sorted: nearby_stations =
            # nearby_stations.sort_values(by='distance', axis=0)
            nearest_stations[nearby_stations.loc[0, 'station_id']] = \
                nearby_stations.loc[0, 'name']

        # get the weather data of those stations
        forecast = dwd_request.filter_by_station_id(
            list(nearest_stations.keys())).values.all().df.to_pandas()
        forecast['name'] = forecast['station_id'].apply(
            lambda u: nearest_stations[u])
        forecast = convert_tz(forecast)
        return forecast

    @staticmethod
    def data_to_graph(df: pd.DataFrame, name: str,
                      light_mode=True) -> dcc.Graph:

        df = df.rename({'date': 'Datum', 'name': 'Wetterstation'}, axis=1)
        # adjust temperature from Kelvin to Celsius
        mask_kelvin = df['parameter'].str.startswith('temperature')
        df.loc[mask_kelvin, 'value'] -= 273.15

        # adjust wind speed from m/s to km/h
        mask_wind = df['parameter'].str.startswith('wind_speed')
        df.loc[mask_wind, 'value'] *= 3.6

        # adjust sunshine duration from seconds to hours
        mask_sun = df['parameter'].str.startswith('sunshine_duration')
        df.loc[mask_sun, 'value'] /= 3600.0

        # create figure https://plotly.com/python/facet-plots/
        figure = px.line(df, x='Datum', y='value', color='Wetterstation',
                         facet_row='parameter', facet_row_spacing=0.05)
        figure.add_hline(y=0, line_dash="solid")

        # adjust annotations
        # https://plotly.com/python/reference/layout/annotations/
        figure.for_each_annotation(
            lambda a: a.update(text=a.text.split("=")[-1].split("_")[0]))
        figure.update_annotations(x=-0.025, xref='paper',
                                  xanchor='right')  # move to the right

        # update axes
        figure.update_yaxes(matches=None, title=None, gridcolor='LightGrey')
        day_min = (date.today() - timedelta(days=0)).strftime('%Y-%m-%d')
        day_max = (date.today() + timedelta(days=4)).strftime('%Y-%m-%d')
        figure.update_xaxes(range=(day_min, day_max), gridcolor='LightGrey')

        # update layout
        figure.update_layout(
            margin=dict(t=20, l=80, b=10, r=5),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5
            ))

        if light_mode:
            figure.update_layout(template='plotly_white')
        else:
            figure.update_layout(template="plotly_dark")

        graph = dcc.Graph(id=name, figure=figure, style={'height': '85vh'})
        return graph
