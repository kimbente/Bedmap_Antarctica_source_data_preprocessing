import os
import pandas as pd
import pyproj

# NOTE: This script might take a while to run and requires sufficient memory

#############################
#### CLEANING PREFERENCES ###
#############################

# Set clearning preferences depending on which variable we are interested in. We will use ice thickness data for now, so we only exclude (i.e. drop) rows without ice thickness.
# NOTE: Of course data may be combined with REMA surface elevation measurements (however with temporal mismatch) to infer missing variables within the s (surface elevation) - t (ice thickness) - b (bed elevation) "triangle". This is a preprocessing preference / design choice the user can make. ("Which variables was interpreted and which was inferred?")

bool_remove_rows_without_ice_thickness = True
bool_remove_rows_without_bed_elevation = False

#############################
### SPECIFY SUBSET REGION ###
#############################

# Set to False if you want only want to generate the full bedmap123 dataset without subsetting
SUBSET = True

# Replace with your desired region name and coordinates. The coordinates are in Antarctic Polar Stereographic (EPSG:3031) projection.

region_name = "byrd" 

# This example covers a 300 x 300 km region over the Byrd catchment
region_x_min = 350_000
region_x_max = 650_000
region_y_min = -1_000_000
region_y_max = -700_000

# Another example for Totten Glacier: 
#
# region_name = "totten"
#
# This example covers a 100 x 100 km region over Totten Glacier
# region_x_min = 2_200_000
# region_x_max = 2_300_000
# region_y_min = -1_050_000
# region_y_max = -950_000

# Another example for Ross Ice Shelf:
#
# region_name = "ross"
#
# This example covers a 1000 x 1000 km region over Ross Ice Shelf
# region_x_min = -600_000
# region_x_max = 400_000
# region_y_min = -1_400_000
# region_y_max = -400_000

#################################
### SPECIFY PATH TO DIRECTORY ###
################################# 

# CHANGE THIS TO YOUR PATH, same as in the step1 download script
path_to_bedmap_data_folder = "/Users/kim.bente/DATA/bedmap_raw_data"

# paths to subfolders
path_to_bedmap1_data_folder = os.path.join(path_to_bedmap_data_folder, "bedmap1_raw_data")
path_to_bedmap2_data_folder = os.path.join(path_to_bedmap_data_folder, "bedmap2_raw_data")
path_to_bedmap3_data_folder = os.path.join(path_to_bedmap_data_folder, "bedmap3_raw_data")

# list all CSVs in the folder
list_of_bedmap1_csv_files = [f for f in os.listdir(path_to_bedmap1_data_folder) if f.endswith(".csv")]
list_of_bedmap2_csv_files = [f for f in os.listdir(path_to_bedmap2_data_folder) if f.endswith(".csv")]
list_of_bedmap3_csv_files = [f for f in os.listdir(path_to_bedmap3_data_folder) if f.endswith(".csv")]

# initialise DataFrame and column names
column_list = ["lon", "lat", "x", "y", "s", "t", "b", "b_inferred", "source", "trajectory_id", "trace_id"]
bedmap123_data = pd.DataFrame(columns = column_list)

# set up coordinate transformer once
lonlat_to_polarstereo = pyproj.Transformer.from_crs(
    crs_from = pyproj.CRS("epsg:4326"), # WGS84 (lon, lat)
    crs_to = pyproj.CRS("epsg:3031"), # Antarctic Polar Stereographic (x, y)
    always_xy = True
)

# lists 
paths_to_data_folders_all_versions = [path_to_bedmap1_data_folder, path_to_bedmap2_data_folder, path_to_bedmap3_data_folder]
list_of_all_versions = [list_of_bedmap1_csv_files, list_of_bedmap2_csv_files, list_of_bedmap3_csv_files]

# Initialise to save meta data
metadata_columns = ["source", "BM_version", "platform", "firn", "doi", ]
metadata_df = pd.DataFrame(columns = metadata_columns)

# loop over bedmap versions
for v, (csv_list, folder_path) in enumerate(zip(list_of_all_versions, paths_to_data_folders_all_versions), start = 1):
    print(f"Processing Bedmap{v}...")
    print(f"Number of bedmap{v} csv files:", len(csv_list))

    # loop over csv files
    for i in csv_list:

        print("Processing:", i)
        # construct full file path
        file_path = os.path.join(folder_path, i)

        # Load metadata only
        i_metadata = pd.read_csv(file_path, nrows = 18, low_memory = False, sep = "#")
        i_platform = i_metadata.iloc[7, 1][10:]
        i_firn = i_metadata.iloc[11, 1][17:]
        i_doi = i_metadata.iloc[10, 1]
        # Add to next line of metadata DataFrame
        metadata_df.loc[len(metadata_df)] = [i, i[-7:-4], i_platform, i_firn, i_doi]

        # Load CSV, skipping metadata header lines
        pd_data = pd.read_csv(file_path, skiprows = 18, low_memory = False)

        # Extract and rename required columns
        df = pd_data[[
            "longitude (degree_east)",
            "latitude (degree_north)",
            "surface_altitude (m)",
            "land_ice_thickness (m)",
            "bedrock_altitude (m)",
            "trajectory_id",
            "trace_number"
        ]].copy() # NOTE: Copy to avoid SettingWithCopyWarning

        # Rename columns to short names
        # NOTE: trajectory_id and trace_id combined can serve as a unique identifier for each measurement point, which can be useful for tracking data provenance and for potential future analyses.
        df.columns = ["lon", "lat", "s", "t", "b", "trajectory_id", "trace_id"]

        # Force float so files where a column is all -9999 (read as int64) can still take float values
        df[["s", "t", "b"]] = df[["s", "t", "b"]].astype("float64")

        # Mark where bedrock elevation is inferred (as this is approximately true)
        df["b_inferred"] = False
        # Create a mask where bedrock elevation is missing (-9999) but surface and land ice thickness are provided
        infer_b_mask = (df['s'] != -9999) & (df['t'] != -9999) & (df['b'] == -9999)
        df.loc[infer_b_mask, 'b_inferred'] = True
        df.loc[infer_b_mask, 'b'] = df['s'] - df['t']

        # Drop rows still missing bed elevation
        # TODO: Change this if we are focussing on ice thickness and not bed elevation
        if bool_remove_rows_without_bed_elevation:
            dropped_rows_b = (df['b'] == -9999).sum()
            print(f"#rows dropped: {dropped_rows_b}")
            df = df[df['b'] != -9999]
        
        if bool_remove_rows_without_ice_thickness:
            dropped_rows_t = (df['t'] == -9999).sum()
            print(f"#rows dropped: {dropped_rows_t}")
            df = df[df['t'] != -9999]

        # Project coordinates 
        df["x"], df["y"] = lonlat_to_polarstereo.transform(df["lon"].values, df["lat"].values)

        # Add filename as source - This is very useful for a lot of preprocessing
        df["source"] = i

        # Ensure column order and append
        df = df[column_list]
        bedmap123_data = pd.concat([bedmap123_data, df], ignore_index = True)

    # End csv_list loop
    # Final check of shape
    print("Combined dataset shape:", bedmap123_data.shape)

# End version loop
print(f"Finished processing Bedmap{v}.")

# Save the combined DataFrame to a CSV file. This step takes a while, so be patient.
# NOTE: This will overwrite the file if it already exists
output_path = os.path.join(path_to_bedmap_data_folder, "bedmap123.csv")
bedmap123_data.to_csv(output_path, index = False)

print(f"Combined dataset saved to {output_path}.")

# Repeat for meta data DataFrame
metadata_path = os.path.join(path_to_bedmap_data_folder, "bedmap123_metadata.csv")
metadata_df.to_csv(metadata_path, index = False)

print(f"Metadata dataset saved to {metadata_path}.")

##################
### SUBSETTING ###
##################

if SUBSET:
    # Subset the DataFrame to the specified region
    bedmap123_data_subset = bedmap123_data[
        (bedmap123_data["x"] >= region_x_min) & (bedmap123_data["x"] <= region_x_max) &
        (bedmap123_data["y"] >= region_y_min) & (bedmap123_data["y"] <= region_y_max)
    ]

    output_path_subset = os.path.join(path_to_bedmap_data_folder, f"bedmap123_subset_{region_name}.csv")
    bedmap123_data_subset.to_csv(output_path_subset, index = False)
    print(f"Subset for {region_name} saved to {output_path_subset}.")