import os

import pandas as pd
import pytz

def convert_tz(df: pd.DataFrame, default_tz='Europe/Berlin') -> pd.DataFrame:
    """ convert time zone information to local time zone """
    # check time zone in environment and set to Berlin if not existing
    tz = os.getenv('TZ')
    try:
        pytz.timezone(tz)
    except:
        tz = default_tz

    date_column = [col for col in df.columns if
                   pd.api.types.is_datetime64_any_dtype(df[col])]
    for col in date_column:
        df[col] = df[col].dt.tz_convert(tz).dt.tz_localize(None)

    return df
