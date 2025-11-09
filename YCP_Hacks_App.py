import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
import os
from io import BytesIO, StringIO
import base64
import numpy as np
from sklearn.metrics import mean_squared_error
from google.cloud import storage
import plotly.graph_objects as go

# Loads in data from both the baseline file path and the file
# path that is currently selected to be graphed, returning
# two dataframes with the cleaned data from each
def clean_data(baseline_df, df):
    baseline_df = baseline_df.iloc[1:]
    baseline_df.columns = ["cm-1", "A"]
    baseline_df["cm-1"] = baseline_df["cm-1"].astype(float)
    baseline_df["A"] = baseline_df["A"].astype(float)

    df = df.iloc[1:]
    df.columns = ["cm-1", "A"]
    df["cm-1"] = df["cm-1"].astype(float)
    df["A"] = df["A"].astype(float)
    return baseline_df, df

# plot figure using plotly, with the x axis being "cm-1" and the y-axis being "A",
# each plot will be between the baseline and the currently selected sample
def plot_figure_plotly(baseline_df, df, baseline_file_name, selected_file_name):
    fig = go.Figure()

    # Add baseline trace
    fig.add_trace(
        go.Scatter(x=baseline_df["cm-1"], y=baseline_df["A"], mode='lines', 
                   name=baseline_file_name, line=dict(color='blue'))
    )

    # Add selected sample trace
    fig.add_trace(
        go.Scatter(x=df["cm-1"], y=df["A"], mode='lines',
                   name=selected_file_name, line=dict(color='green'))
    )

    # Update layout
    fig.update_layout(
        title=dict(
            text="Graph of Selected Sample Compared to Baseline File",
            x=0.5,            
            xanchor='center',
            font=dict(size=24, family="Arial, sans-serif", color="black")
        ),
        xaxis_title="cm-1",
        yaxis_title="A",
        xaxis=dict(range=[4000, 500], autorange=False),
        yaxis=dict(tick0=0, dtick=0.5, range=[0,6]),
        legend=dict(orientation="h", yanchor="bottom", y=-0.2,           
                    xanchor="center", x=0.5,
                    font=dict(size=12, family="Arial, sans-serif", color="black")
                   )
    )
    return fig

# Cloud setup and data pull
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "C:/Users/natha/Downloads/ycp-hackathon-e6f46540bbaf.json"
bucket_name = "mrg_labs_data"
client = storage.Client()
bucket = client.bucket(bucket_name)
blobs = list(bucket.list_blobs())
files_in_folder = [blob.name for blob in blobs if blob.name.endswith(".csv")]

# streamlit setup
st.set_page_config(page_title="My Streamlit App", layout="wide")
st.title("MRG Labs Batch Plotting Tool")
st.write("Select the baseline file from the first dropdown below. In the second dropdown, you can select multiple files to use as samples. The third dropdown allows you to select which sample to be plotted on the graph against the baseline.")

# create select boxes to choose the baseline file, the files to compare with the baseline,
# and the file to be graphed against the baseline on the user interface
baseline_file_name = st.selectbox("Select a file to as the baseline", files_in_folder)
file_name = st.multiselect("Select a file to compare with baseline", files_in_folder)
selected_file_name = st.selectbox("Choose graph to display", file_name)

# once a file has been selected to be graphed, this loop begins
if selected_file_name:
    # pull both baseline file and selected file from cloud
    blob = bucket.blob(baseline_file_name)
    content = blob.download_as_text()
    baseline_df = pd.read_csv(StringIO(content))
    
    blob = bucket.blob(selected_file_name)
    content = blob.download_as_text()
    df = pd.read_csv(StringIO(content))
    
    # clean data and create plot comparing baseline and sample
    baseline_df, df = clean_data(baseline_df, df)
    fig = plot_figure_plotly(baseline_df, df, baseline_file_name, selected_file_name)
    img_buffer = BytesIO()
    img_buffer.seek(0)
    col1, col2 = st.columns(2)
    with col1:
        fig.update_layout(width=700, height=700)
        st.plotly_chart(fig)

    # calculate mse over different periods of the graph
    df_new = df[~df.index.isin(range(400, 800)) & ~df.index.isin(range(3260, 3280))]
    baseline_new = baseline_df[~baseline_df.index.isin(range(400, 800)) & ~baseline_df.index.isin(range(3260, 3280))]
    mse = mean_squared_error(baseline_df['A'], df['A'])
    oxidation_mse = mean_squared_error(baseline_df['A'].iloc[3260:3280], df['A'].iloc[3260:3280])
    water_damage_mse = mean_squared_error(baseline_df['A'].iloc[400:800], df['A'].iloc[400:800])
    confirmation_mse = mean_squared_error(baseline_new['A'], df_new['A'])
    print("MSE: ", mse)
    print("Confirmation MSE: ", confirmation_mse)
    print("Oxidation MSE: ", oxidation_mse)
    print("Water Damage MSE: ", water_damage_mse)

    # calculate overall score rating using mse values
    overall_score = 1/(confirmation_mse * 40 + oxidation_mse * 30 + water_damage_mse)
    print("Overall Score: ", overall_score )
    status = " "
    if overall_score > 0.45:
        status = "Green"
        color = "🟢"
    elif overall_score > 0.15:
        status = "Yellow"
        color = "🟡"
    else:
        status = "Red"
        color = "🔴"
    
    mse_values = [mse, confirmation_mse, oxidation_mse, water_damage_mse]
    labels = ["Overall", "Confirmation", "Oxidation", "Water Damage"]

    fig2, ax = plt.subplots()
    colors = ['#ADEBB3', '#F0AD4E', '#D9534F','skyblue' ]
    ax.bar(labels, mse_values, color= colors)
    ax.set_xlabel("Types of Mean Squared Error")
    ax.set_ylabel("Mean Squared Error Value")
    ax.set_title("Mean Squared Error for Current Plot")
    with col2:
       st.pyplot(fig2)

    # Show threshold relating to overall score
    st.write("Thresholds -> Red: Score < 0.15, Yellow: 0.15 <= Score < 0.45, Green: Score >= 0.45")
    st.write("Overall Score: ", overall_score)
    if status == "Red":
            status_level = "Red Status"
            st.error(f"**{status_level}**", icon="🚨")
    elif status == "Yellow":
            status_level = "Yellow Status"
            st.warning(f"**{status_level}**", icon="⚠️")
    else:
            status_level = "Green Status"
            st.success(f"**{status_level}**", icon="✅")
    save_path = st.text_input("Enter folder path for download:")
    if st.button("Download All Figures"):
        if save_path:
            # modify save_path to allow the user to simply use "copy path"
            # for the folder name if they choose to, which means removing quotes
            # at the beginning and end and replacing "\\" with "/"
            save_path = save_path.strip()
            if(save_path.startswith('"') and save_path.endswith('"')):
                save_path = save_path[1:-1]
            elif(save_path.startswith('"')):
                save_path = save_path[1:]
            elif(save_path.endswith('"')):
                save_path = save_path[:-1]
            save_path = save_path.replace("\\", "/")
            # for each file that is selected in the sample select box, we will load in
            # load and clean both the baseline and the selected file, plot the figure, and save
            # it to the selected file save_path with a name in the format "{file_1}_{file_2}"
            for file in file_name:
                file_without_extension, ext = os.path.splitext(file)
                baseline_file_without_extension, ext = os.path.splitext(baseline_file_name)
                file_to_save = "_".join([baseline_file_without_extension, file_without_extension])
                overall_path = "/".join([save_path, file_to_save])
                overall_path += ".png"

                blob = bucket.blob(baseline_file_name)
                content = blob.download_as_text()
                baseline_df = pd.read_csv(StringIO(content))
    
                blob = bucket.blob(file)
                content = blob.download_as_text()
                df = pd.read_csv(StringIO(content))
            
                baseline_df, df = clean_data(baseline_df, df)

                fig = plot_figure_plotly(baseline_df, df, baseline_file_name, selected_file_name)
                img_buffer = BytesIO()
                img_bytes = fig.to_image(format="png")
                img_buffer.write(img_bytes)
                img_buffer.seek(0)
                fig.write_image(overall_path, format="png")
                st.success(f"Saved figure to: {overall_path}")
