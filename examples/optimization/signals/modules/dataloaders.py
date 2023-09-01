from __future__ import annotations

import os.path
from typing import Tuple, cast

import numpy as np
import numpy.typing as npt
import pandas as pd


def get_c02_data() -> pd.DataFrame:
    path = "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_weekly_mlo.csv"
    df = pd.read_csv(
        path,
        # column names on row 35, data starts on row 56
        skiprows=34,
        index_col=False,
        na_values=[-999.99],
    )
    # group by year and count the number of rows for each year
    year_counts = df.groupby("year").count()
    # find the years with less than 53 rows
    missing_years = year_counts[year_counts["decimal"] < 53].index.tolist()[
        1:-1
    ]
    new_rows = [df]
    # make every year have exactly 53 entries by inserting NaNs at the end of
    # the year
    for year in missing_years:
        num_blank_rows = 53 - year_counts.loc[year]["decimal"]
        # Create a new DataFrame with blank rows and the same columns as the
        # original
        blank_rows = pd.DataFrame(
            np.nan, index=np.arange(num_blank_rows), columns=df.columns
        )
        blank_rows["year"] = year
        blank_rows["decimal"] = year + 0.995
        # Append the current year's rows to the list of new rows
        new_rows.append(blank_rows)
    return pd.concat(new_rows).sort_values("decimal")


def make_changepoint_data(
    seed: int = 243, include_periodic_component: bool = False
) -> Tuple[npt.NDArray, npt.NDArray]:
    np.random.seed(seed)
    true = np.ones(1000) * 12
    true[400:] -= 1.5
    msk = np.logical_and(
        np.arange(1000) > 600, (np.arange(1000) // 100) % 2 == 0
    )
    true[msk] += 1
    msk = np.logical_and(
        np.arange(1000) > 750, (np.arange(1000) // 100) % 2 == 0
    )
    true[msk] += 1
    noise = np.random.randn(1000) * 0.15
    if include_periodic_component:
        xs = np.arange(len(true))
        smooth_per = np.sin(xs * 2 * np.pi / 400)
        y = true + noise + smooth_per
        return y, np.c_[noise, true, smooth_per].T
    else:
        y = true + noise
        return y, np.c_[noise, true].T


def get_pvdaq_data() -> pd.DataFrame:
    path = "../data/pvdaq_data.csv"
    if not os.path.isfile(path):
        from solardatatools import get_pvdaq_data

        pv_df = cast(
            pd.DataFrame,
            get_pvdaq_data(sysid=34, year=2011, api_key="DEMO_KEY"),
        )
    else:
        pv_df = pd.read_csv(path, index_col=0)
        pv_df.index = pd.DatetimeIndex(pv_df.index, freq="900S")
        pv_df = pv_df.sort_index()

    pv_df.loc[pv_df["dc_power"] < 0, "dc_power"] = np.nan
    return pv_df


def make_soiling_data(seed: int = 243) -> Tuple[pd.DataFrame, str]:
    np.random.seed(seed)

    def simulate_PV_time_series(
        first_date,
        last_date,
        freq="1D",
        degradation_rate=-0.005,
        noise_scale=0.01,
        seasonality_scale=0.01,
        nr_of_cleaning_events=120,
        soiling_rate_low=0.0001,
        soiling_rate_high=0.003,
        smooth_rates=False,
        random_seed=False,
    ):
        if random_seed:  # Have seed for repeatability
            if not type(np.random.seed) == int:
                np.random.seed(int(random_seed))

        # Initialize time series and data frame
        times = pd.date_range(first_date, last_date, freq=freq)
        df = pd.DataFrame(
            index=times,
            columns=[
                "day",
                "noise",
                "seasonality",
                "degradation",
                "soiling",
                "cleaning_events",
            ],
        )
        n = len(times)

        df["day"] = range(n)
        df["noise"] = np.random.normal(1.0, scale=noise_scale, size=n)
        df["seasonality"] = (
            seasonality_scale * np.sin(df["day"] / 365.25 * 2 * np.pi) + 1
        )
        df["degradation"] = 1 + degradation_rate / 365.25 * df["day"]

        # simulate soiling
        cleaning_events = np.random.choice(
            df["day"], nr_of_cleaning_events, replace="False"
        )
        cleaning_events = np.sort(cleaning_events)

        x = np.full(n, 1)
        intervals = np.split(x, cleaning_events)
        soiling_rate = []
        for interval in intervals:
            rate = np.random.uniform(
                low=soiling_rate_low, high=soiling_rate_high, size=1
            ) * np.ones(len(interval))
            soiling_rate.append(rate)
        df["soiling_rate"] = np.concatenate(soiling_rate)
        if smooth_rates:
            df.soiling_rate = (
                df.soiling_rate.rolling(smooth_rates, center=True)
                .mean()
                .ffill()
                .bfill()
            )
        derate = np.concatenate(
            [
                np.cumsum(si)
                for si in np.split(df["soiling_rate"].values, cleaning_events)
            ]
        )
        df["soiling"] = 1 - derate

        # Generate Performance Indexes
        df["PI_no_noise"] = (
            df["seasonality"] * df["degradation"] * df["soiling"]
        )
        df["PI_no_soil"] = df["seasonality"] * df["degradation"] * df["noise"]
        df["PI_no_degrad"] = df["seasonality"] * df["soiling"]
        df["daily_norm"] = df["noise"] * df["PI_no_noise"]

        return df

    def simulate_PV_time_series_seasonal_soiling(
        first_date,
        last_date,
        freq="1D",
        degradation_rate=-0.005,
        noise_scale=0.01,
        seasonality_scale=0.01,
        nr_of_cleaning_events=120,
        soiling_rate_center=0.002,
        soiling_rate_std=0.001,
        soiling_seasonality_scale=0.9,
        random_seed=False,
        smooth_rates=False,
        seasonal_rates=False,
    ):
        """As the name implies, this function models soiling rates that vary from day to day according
        to a Gaussian distribution"""
        if random_seed:  # Have seed for repeatability
            if not type(np.random.seed) == int:
                np.random.seed(int(random_seed))

        # Initialize time series and data frame
        times = pd.date_range(first_date, last_date, freq=freq)
        df = pd.DataFrame(index=times)
        n = len(times)

        df["day"] = range(n)
        df["noise"] = np.random.normal(1.0, scale=noise_scale, size=n)
        df["seasonality"] = (
            seasonality_scale * np.sin(df["day"] / 365.25 * 2 * np.pi) + 1
        )
        df["degradation"] = 1 + degradation_rate / 365.25 * df["day"]

        soiling_seasonality = (
            soiling_rate_center
            * soiling_seasonality_scale
            * np.sin(
                df["day"] / 365.25 * 2 * np.pi
                + np.random.uniform(10, size=1) * np.pi
            )
        )
        cleaning_probability = (
            2 - soiling_seasonality_scale
        ) * soiling_seasonality.max() + soiling_seasonality
        cleaning_probability /= cleaning_probability.sum()

        # simulate soiling
        cleaning_events = np.random.choice(
            df["day"].values,
            nr_of_cleaning_events,
            replace="False",
            p=cleaning_probability.values,
        )
        cleaning_events = np.sort(cleaning_events)
        df["cleaning_events"] = [
            True if day in cleaning_events else False for day in df.day
        ]

        x = np.full(n, 1)
        intervals = np.split(x, cleaning_events)
        soiling = []
        soiling_rate = []
        for interval in intervals:
            if len(soiling) > 0:
                pos = len(np.concatenate(soiling))
            else:
                pos = 0
            if seasonal_rates:
                if smooth_rates:
                    soiling_season = soiling_seasonality[
                        pos : pos + len(interval)
                    ]
                    rate = np.random.normal(
                        soiling_rate_center + soiling_season,
                        soiling_rate_std,
                        size=len(interval),
                    )
                else:
                    soiling_season = soiling_seasonality[pos]
                    rate = np.random.normal(
                        soiling_rate_center + soiling_season,
                        soiling_rate_std,
                        size=1,
                    ) * np.ones(len(interval))
            else:
                if smooth_rates:
                    print("Smooth rates not possible without seasonal rates")
                soiling_season = 0
                rate = np.random.normal(
                    soiling_rate_center + soiling_season,
                    soiling_rate_std,
                    size=1,
                ) * np.ones(len(interval))
            derate = 1 - np.matmul(half_one_matrix(len(interval)), rate)
            soiling.append(derate)
            soiling_rate.append(rate)
        df["soiling"] = np.concatenate(soiling)
        df["soiling_rate"] = np.concatenate(soiling_rate)

        # Generate Performance Indexes
        df["PI_no_noise"] = (
            df["seasonality"] * df["degradation"] * df["soiling"]
        )
        df["PI_no_soil"] = df["seasonality"] * df["degradation"] * df["noise"]
        df["PI_no_degrad"] = df["seasonality"] * df["soiling"]
        df["daily_norm"] = df["noise"] * df["PI_no_noise"]

        return df

    def generate_my_soiling_signals(
        high=0.02, low=0.01, index_form="Datetime"
    ):
        first_date = "2010/01/01"
        last_date = "2020/01/01"
        noises = [low, low, high, low, low, low]
        seasonality_scales = [low, high, low, low, low, low]
        soiling_levels = [0.003, 0.001, 0.001, 0.0005, 0.0005, 0.0001]
        names = [
            "normal",
            "M Soil, H season",
            "M Soil, H noise",
            "Seasonal cleaning",
            "L/M Soil (.0005)",
            "Low Soil (.0001)",
        ]
        dfs = []
        for i in range(6):
            if i == 3:
                df = simulate_PV_time_series_seasonal_soiling(
                    first_date,
                    last_date,
                    noise_scale=noises[i],
                    seasonality_scale=seasonality_scales[i],
                    soiling_rate_std=0,
                    soiling_rate_center=soiling_levels[i],
                    soiling_seasonality_scale=0.95,
                    smooth_rates=False,
                    seasonal_rates=False,
                )
            else:
                df = simulate_PV_time_series(
                    first_date,
                    last_date,
                    noise_scale=noises[i],
                    seasonality_scale=seasonality_scales[i],
                    nr_of_cleaning_events=120,
                    soiling_rate_low=0,
                    soiling_rate_high=soiling_levels[i],
                    degradation_rate=-0.005,
                )
            if index_form == "numeric":
                df.index = np.arange(len(df))

            dfs.append(df)

        return dfs, names

    def half_one_matrix(size):
        dummy = np.zeros((size, size))
        dummy[np.triu_indices(size, k=1)] = 1
        return dummy.T

    dfs, _ = generate_my_soiling_signals()
    names = [
        "Base case (max soiling rate = 0.3 %/d)",
        "Double seasonality (max soiling rate = 0.1% per day)",
        "Double noise (max soiling rate = 0.1 %/d)",
        "Seasonal cleaning (constant soiling rate = 0.05 %/d)",
        "Little soiling (max soiling rate = 0.05%/d)",
        "Very little soiling (max soiling rate = 0.01 %/d)",
    ]
    ss_df = dfs[1]
    return cast(pd.DataFrame, ss_df), names[1]
