# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/01_embeddings.ipynb.

# %% auto 0
__all__ = ['EmbeddingsFactory', 'EmbeddingsHandler']

# %% ../nbs/01_embeddings.ipynb 2
import math
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import List

import contextily as ctx
import geopandas as gpd
import matplotlib.pyplot as plt
import nbdev
import numpy as np
import pandas as pd
import rasterio
from nbdev.showdoc import show_doc
from shapely.geometry import Point
from tqdm import tqdm

# %% ../nbs/01_embeddings.ipynb 6
class EmbeddingsFactory:
    def __init__(self, model, output_directory):
        """
        Initializes the Embeddings Factory with a model and an output directory.
        """
        self.model = model
        self.output_directory = output_directory

    def generate_embeddings(self, location_geojson, start_date, end_date, source):
        """
        Generates embeddings for a given location and time range.
        """

    def _save_embeddings(self, embeddings, feature, start_date, end_date):
        """
        Saves the embeddings to a file or S3.
        """

# %% ../nbs/01_embeddings.ipynb 9
class EmbeddingsHandler:
    def __init__(
        self,
        path: Path,  # Path to the file or folder with files
        max_files: [None, int] = None,
    ):  # Max number of files to load, randomly chosen
        self.path = Path(path)
        self.gdf = None
        self.files = None

        # handle path
        if self.path.is_dir():
            self.files = list(self.path.glob("*.gpq"))
            if max_files is not None:
                rng = np.random.default_rng()
                self.files = rng.choice(self.files, size=max_files, replace=False)
            assert len(self.files) > 0, "No gpq files found in path"
        else:
            self.files = [self.path]
            assert self.path.suffix == ".gpq", "File must be a gpq file"
        self.load_geoparquet_folder()

    def load_geoparquet_folder(
        self,
    ):
        "Load geoparquet files calling read_embeddings_file in parallel"
        with ProcessPoolExecutor() as executor:
            gdfs = list(
                tqdm(
                    executor.map(self.read_geoparquet_file, self.files),
                    total=len(self.files),
                )
            )
        print(f"Total rows: {sum([len(gdf) for gdf in gdfs])}\n Merging dataframes...")
        gdf = pd.concat(gdfs, ignore_index=True)
        gdf = gdf.drop('index', axis=1)
        self.gdf = gdf
        print("Done!\n Total rows: ", len(self.gdf))

    def read_geoparquet_file(self, file: Path):  # Path to the geoparquet file
        """
        Reads a geoparquet file and returns a dataframe with the embeddings.
        """
        assert file.exists(), "Path does not exist"
        # check pattern of file name like 33PWP_20181021_20200114_v001.gpq
        assert file.suffix == ".gpq", "File must be a gpq file"
        parts = file.stem.split("_")
        n_parts = len("33PWP_20181021_20200114_v001".split("_"))
        assert len(parts) == n_parts, "File name must have 4 parts"
        location, start_date, end_date, version = parts

        # read file
        gdf = gpd.read_parquet(file)
        gdf = gdf.to_crs("EPSG:3857")

        # add centroid x and y columns
        gdf["x"] = gdf.geometry.centroid.x
        gdf["y"] = gdf.geometry.centroid.y

        # set columns for the values of location, start_date, end_date, version
        gdf["location"] = location
        gdf["start_date"] = datetime.strptime(start_date, "%Y%m%d")
        gdf["end_date"] = datetime.strptime(end_date, "%Y%m%d")
        gdf["version"] = version
        return gdf

    def transform_crs(self, crs="epsg:3857"):  # CRS to transform to
        """
        Transforms the CRS of the dataframe.
        """
        self.gdf = self.gdf.to_crs(crs)

    def plot_locations(
        self,
        figsize: [int, int] = (10, 10),  # Size of the plot
        alpha: float = 0.2,  # Transparency of the points
        max_rows: [int, None] = 10000,  # Random max number of rows to plot
        bounds: List[int] = None, # Bounds of the plot [xmin, ymin, xmax, ymax]
        indices: List[int] = None # Indices of the rows to plot
    ):
        """
        Plots the dataframe on a map with an OSM underlay.
        """

        # Default to all indices if none are provided
        if indices is None:
            indices = self.gdf.index.values

        if max_rows is not None and len(indices) > max_rows:
            self.gdf = self.gdf.drop_duplicates(subset=["geometry"])
            rng = np.random.default_rng()
            indices = rng.choice(indices, size=max_rows, replace=False)
        ax = self.gdf.loc[indices].plot(
                figsize=figsize, alpha=alpha, edgecolor='k', markersize=1
            )

        # If bounds are provided, set the bounds of the plot
        if bounds is not None:
            ax.set_xlim(bounds[0], bounds[2])
            ax.set_ylim(bounds[1], bounds[3])

        ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik)
        ax.set_axis_off()
        plt.show()

    def fetch_and_plot_image(
        self,
        index: int,  # index of the row to plot
        local_folder: Path,  # Local folder to save the image
        force_fetch: bool,  # Whether to force fetching the image
        bands: List[int] = [3, 4, 2],
    ):  # Bands to read
        """
        Fetches an image from a URL or local path, reads RGB bands, and plots it.
        """
        row = self.gdf.loc[index]

        if force_fetch:
            # print(f"Fetching image for row {index}")
            url = row["source_url"]
            local_path = local_folder / Path(url).name
            assert local_folder.exists(), f"Local folder {local_path} does not exist"
            with rasterio.open(url) as src:
                # print(f"Reading {bands} bands from {url}")
                rgb = src.read(bands)
            with rasterio.open(
                local_path,
                "w",
                driver="GTiff",
                height=rgb.shape[1],
                width=rgb.shape[2],
                count=len(bands),
                dtype=rgb.dtype,
                crs=src.crs,
                transform=src.transform,
            ) as dst:
                # print(f"Writing {bands} bands to {local_path}")
                dst.write(rgb)
                self.gdf.loc[self.gdf["source_url"] == url, "local_path"] = local_path
        else:
            #print(f"Reading local image for row {index}")
            local_path = row["local_path"]
            with rasterio.open(local_path) as src:
                # print(f"Reading {bands} bands from {local_path}")
                rgb = src.read()
        rgb = (rgb - rgb.min()) / (rgb.max() - rgb.min())
        rgb = np.transpose(rgb, [1, 2, 0])

        #clip values on each band to 10-90 percentile
        percentiles = np.percentile(rgb, [10, 90], axis=(0, 1))
        rgb = np.clip(rgb, percentiles[0], percentiles[1])
        return rgb

    def rgb_imgs(
        self,
        row_indices: int | List[int],  # Indices of the rows to plot
        local_folder: Path = None,  # Local folder to save the image
        force_fetch: bool = False,
    ):
        """
        Plots RGB images for specified rows,
        either from local storage or by fetching them.
        """

        if isinstance(row_indices, int):
            row_indices = [row_indices]

        # create column 'local_path' if it doesn't exist
        if "local_path" not in self.gdf.columns:
            # print("Creating new column 'local_path'")
            self.gdf["local_path"] = None

        # check if local_path exists on the row
        for i in row_indices:
            row = self.gdf.loc[i]
            if row["local_path"] is None:
                # print(f"local_path not found for row {index}")
                force_fetch = True

        if force_fetch and local_folder is None:
            # check if local_path values are all not None,
            # take the path of the first instance
            if self.gdf["local_path"].notnull().any():
                existing_files = self.gdf[self.gdf["local_path"].notnull()].iloc[0]
                local_folder = Path(existing_files["local_path"]).parent
            else:
                raise ValueError("local_folder must be provided if force_fetch is True")

        num_images = len(row_indices)
        num_cols = min(3, num_images)
        num_rows = math.ceil(num_images / num_cols)

        fig, axes = plt.subplots(
            nrows=num_rows, ncols=num_cols, figsize=(5 * num_cols, 5 * num_rows)
        )
        if num_images == 1:
            axes = [axes]
        else:
            axes = axes.flatten()

        for idx, index in enumerate(row_indices):
            rgb = self.fetch_and_plot_image(index, local_folder, force_fetch)
            axes[idx].imshow(rgb)
            axes[idx].axis("off")
            # axes[idx].set_title(f"{Path(self.gdf.iloc[index]['local_path']).stem}")

        # Hide any unused subplots
        for ax in axes[num_images:]:
            ax.axis("off")

        plt.tight_layout()
        plt.show()