#!/usr/bin/env python 3.11.0
# -*-coding:utf-8 -*-
# @Author  : Shuang (Twist) Song
# @Contact   : SongshGeo@gmail.com
# GitHub   : https://github.com/SongshGeo
# Website: https://cv.songshgeo.com/

from typing import List, Union

import geopandas as gpd
import pandas as pd
import pint_pandas
import pkg_resources
from IPython import display
from matplotlib import pyplot as plt
from pint import UnitRegistry

NAME = r"/data/Zhou et al_2020_PNAS_dataset.xlsx"
PNAS_DATA = pkg_resources.resource_filename("src", NAME)

# YR_GDF = gpd.read_file(r"data/source/YR_shapefile/huanghe.shp")

ITEMS = pkg_resources.resource_filename("src", "data/items.json")
MAP = pkg_resources.resource_filename("src", "data/GIS Shapefile/perfectures.shp")


MULTI_ITEMS_COLS = [
    "Industrial WUI",
    "Industrial gross value added (GVA)",
    "Irrigation water-use intensity (WUI)",
    "Irrigated area",
]

Units = {
    "Irrigation water-use intensity (WUI)": "mm * kha**-1",
    "Irrigated area": "kha",
    "Total water use": "km ** 3",
    "IRR": "km ** 3",
}

ureg = UnitRegistry()  # 注册单位
# 使用这里的注册单位成为 Pandas-pint 的注册单位，详见：
# https://github.com/hgrecco/pint-pandas/blob/master/notebooks/pint-pandas.ipynb
pint_pandas.PintType.ureg = ureg

# 为了让pandas-pint 可以画图，需要这样注册，详见：
# https://github.com/hgrecco/pint-pandas/blob/master/notebooks/pint-pandas.ipynb
pint_pandas.PintType.ureg.setup_matplotlib()
ureg.define("TMC = 1e8 m ** 3")


IND = [
    "Textile",
    "Papermaking",
    "Petrochemicals",
    "Metallurgy",
    "Mining",
    "Food",
    "Cements",
    "Machinery",
    "Electronics",
    "Thermal electrivity",
    "Others",
]

IRR = ["Rice", "Wheat", "Maize", "Vegetables and fruits", "Others"]


class ChineseWater:
    def __init__(self, data_path: str = PNAS_DATA, language: str = "en"):
        self._origin = pd.read_excel(data_path, sheet_name="D1", header=[0, 1])
        self._general_cols = ["City_ID", "Year"]
        self._total_cols = ["Total water use", "IND", "IRR", "RUR", "URB"]
        self._crops = IRR
        self._industries = IND
        self._multi_items_cols = MULTI_ITEMS_COLS
        self._active = {}
        self._parse_items()
        self._language = language  # todo: language selection

    def __repr__(self):
        display.display(self.show_data())
        return f"<[Chinese Water Use] {len(self.cities)} cities, {len(self.active_cols)} items.>"

    @property
    def years(self):
        return self.active["Year"].unique()

    @property
    def cities(self):
        return self.active["City_ID"].unique()

    @property
    def active_cols(self):
        return self.origin.columns.levels[0].to_list()

    @property
    def active(self) -> dict:
        return self._active

    @active.setter
    def active(self, value: dict):
        self._active = value

    @property
    def origin(self) -> pd.DataFrame:
        return self._origin

    @origin.setter
    def origin(self, value: pd.DataFrame):
        self._origin = value
        self._parse_items()

    @property
    def versions(self):
        return pint_pandas.show_versions()

    @property
    def index(self):
        return pd.concat([self._active[c] for c in self._general_cols], axis=1)

    @property
    def geodf(self):
        return self.to_spatial(self.cities)

    def _get_item_data(
        self, item: str, folding: bool = True
    ) -> Union[pd.Series, pd.DataFrame]:
        """
        根据

        Args:
            item (str): _description_
            folding (bool, optional): _description_. Defaults to True.

        Returns:
            Union[pd.Series, pd.DataFrame]: _description_
        """
        if item in self._multi_items_cols:
            data = self.active[item]
            if folding:
                item_data = data["Total"]
                item_data.name = item
            else:
                item_data = data.drop("Total", axis=1)
        elif item in self.active_cols:
            item_data = self.active[item]
        return item_data

    def show_data(self, folding: bool = True, sep: str = ":") -> pd.DataFrame:
        dataset = []
        for col in self.active_cols:
            data = self._get_item_data(col, folding)
            # show as this pattern: [level1: level2]
            if isinstance(data, pd.DataFrame):
                data.columns = [col + sep + c for c in data.columns]
            dataset.append(data)
        return pd.concat(dataset, axis=1)

    def show_items(self):
        return pd.read_json(ITEMS).set_index("item")

    def _parse_items(self):
        active = {}
        for col in self.active_cols:
            tmp_df = self.origin[col]
            if col in self._multi_items_cols:
                use_col = tmp_df
            else:
                use_col = tmp_df.iloc[:, 0]
                use_col.name = col
            active[col] = use_col
        self.active = active

    def _filter_general_cols(self, items: List[str]) -> List[str]:
        return list(set(items) - set(self._general_cols))

    def get_item(self, item: str, unit: bool = True) -> pd.DataFrame:
        """读取周丰老师中国用水数据的函数，选取某个项目"""
        selected = self._get_item_data(item, folding=False)
        # 获得带单位的输出
        if unit:
            unit = self.get_unit_of_item(item)
            selected = selected.astype(unit)
        # 选择该 general_cols 和该 item 下的数据
        return pd.concat([self.index, selected], axis=1)

    def replenish_index(
        self, data: Union[pd.Series, pd.DataFrame], name: str = "Unnamed"
    ) -> pd.DataFrame:
        if isinstance(data, pd.Series) and pd.Series.name is None:
            data.name = name
        return pd.concat([self.index, data], axis=1)

    def get_unit_of_item(self, item):
        try:
            unit = f"pint[{Units[item]}]"
        except KeyError as e:
            raise e(f"Not registered unit of item: '{item}'!") from e
        return unit

    def filter_prefectures(
        self, cities: List[str], as_origin: bool = False
    ) -> pd.DataFrame:
        """筛选合适特定的地级市"""
        tmp_data = self.origin.droplevel(1, axis=1)
        filtered = tmp_data[tmp_data["City_ID"].isin(cities)]
        filtered.columns = self.origin.columns
        if as_origin:
            self.origin = filtered
        return filtered

    @staticmethod
    def convert_unit(df: pd.DataFrame, cols: List[str], to: str) -> pd.DataFrame:
        """将数据集里的特定列转化成指定的单位"""
        result = df.copy()
        for col in df:
            if col in cols:
                result[col] = df[col].pint.to(to)
        return result

    def to_spatial(self, cities: List[str]) -> gpd.GeoDataFrame:
        gdf = gpd.read_file(MAP)
        return gdf[gdf["Perfecture"].isin(cities)]

    def viz_item_spatially(self, item, year: Union[int, str] = "mean"):
        pass

    def provincial_group(self, data, year: Union[int, str], agg: str = "mean"):
        name = data.name
        data = self.replenish_index(data)
        if type(year) is int:
            query = data[data["Year"] == year]
        elif type(year) is str:
            query = data.groupby("City_ID")[name].agg(agg).reset_index()
        df = pd.merge(
            left=query,
            right=self.geodf,
            left_on="City_ID",
            right_on="Perfecture",
            how="left",
        )
        return gpd.GeoDataFrame(df)

    def combine_province(self, data):
        return pd.merge(
            left=data,
            right=self.geodf[["Perfecture", "Province_n"]],
            left_on="City_ID",
            right_on="Perfecture",
            how="left",
        )

    def dequantify(self, data):
        return data.pint.dequantify().droplevel(1, axis=1)

    def combine_spatial(self, data: pd.Series):
        data = data.reset_index()
        merged = pd.merge(
            left=data,
            right=self.geodf,
            left_on="City_ID",
            right_on="Perfecture",
            how="left",
        )
        return gpd.GeoDataFrame(merged)

    def scaled_plots(self, data, column, shapefile, ax=None, **kwargs):
        if ax is None:
            _, ax = plt.subplots()
        if isinstance(data, gpd.GeoDataFrame):
            pass
        elif isinstance(data, pd.DataFrame):
            data = gpd.GeoDataFrame(data)
        elif isinstance(data, pd.Series):
            data = self.combine_spatial(data)
        data = gpd.GeoDataFrame(self.dequantify(data))
        legend = kwargs.pop("legend", False)
        ax = shapefile.boundary.plot(edgecolor="black", lw=1, ls=":", label="YR", ax=ax)
        ax = data.plot(
            ax=ax,
            column=column,
            cmap="Reds",
            edgecolor="white",
            linewidth=0.5,
            scheme="NaturalBreaks",
            k=5,
            legend=legend,
            legend_kwds={
                "loc": "upper left",
                "title": f"{column}",
            },
            **kwargs,
        )
        ax.grid(color="lightgray", ls="--")
        ax.set_xlabel("Longitude [$Degree$]")
        ax.set_ylabel("Latitude [$Degree$]")
        return ax