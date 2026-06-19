import streamlit as st
import plotly.express as px
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. Streamlit Page Setup ---
st.set_page_config(page_title="Warehouse Floor Plan Heatmap", page_icon="📦", layout="wide")
st.title("📦 Warehouse Floor Plan Heatmap")
st.markdown(
    "Top-down physical view of warehouse performance. Aisles are split into Odd/Even rows, with a main cross-aisle separating sections A-I and J-Z.")


# --- 2. Data Loading & Generation ---
@st.cache_data
def generate_simulated_data():
    """Generates dummy data spanning Aisles A-Z with Odd/Even Bays."""
    np.random.seed(42)
    # Aisles A through Z
    aisles = [chr(i) for i in range(ord('A'), ord('Z') + 1)]
    # Bays 01 through 20 (Odd and Even)
    bays = [f"{i:02d}" for i in range(1, 21)]
    shelves = ['A', 'B', 'C', 'D']
    bins = ['01', '02', '03']

    data = []
    for _ in range(3000):
        loc = f"{np.random.choice(aisles)}.{np.random.choice(bays)}.{np.random.choice(shelves)}.{np.random.choice(bins)}"
        sales = np.random.randint(1, 150)
        data.append({'Item': f"ITEM_{np.random.randint(1000, 9999)}", 'Location': loc, 'Quantity': sales})
    return pd.DataFrame(data)


st.sidebar.header("Data Source")
uploaded_file = st.sidebar.file_uploader("Upload your warehouse CSV", type=['csv'])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.sidebar.success("File successfully loaded!")
else:
    st.info("Upload your own CSV in the sidebar to update the map.")
    #df = generate_simulated_data()

# --- 3. Data Processing (Physical Mapping) ---
try:
    # --- Outlier Adjustment Line ---
    # Sort by sales descending to compare each sale to the next largest
    df = df.sort_values(by='LineCount', ascending=False).reset_index(drop=True)

    # Calculate the gap between the current sale and the next largest sale
    # (.diff(-1) looks at the row below it in a descending sorted list)
    sales_gap = df['LineCount'].diff(-1)

    df['Adjusted Values'] = np.where(sales_gap > 500, df["Location"], False)
    st.write("Adjusted Outliers are: {}".format(str((df.loc[df['Adjusted Values'] != False]))))
    # If the gap is > 1000, reduce the quantity 5x (Sales / 5), otherwise keep it as is
    df['LineCount'] = np.where(sales_gap > 1000, df['LineCount'] / 5, df['LineCount'])


    # Split the location string
    df[['Aisle', 'Bay', 'Shelf', 'Bin']] = df['Location'].str.split('.', expand=True)

    # Convert Bay to integer to calculate Parity (Odd/Even) and physical Depth
    df['Bay_Num'] = df['Bay'].astype(int)

    # Identify if the row is on the Odd or Even side of the aisle
    df['Row_Side'] = np.where(df['Bay_Num'] % 2 != 0, 'Odd', 'Even')

    # Combine Aisle and Side for X-axis (e.g., "A (Odd)", "A (Even)")
    df['Aisle_Row'] = df['Aisle'] + " " + df['Row_Side']

    # Calculate "Bay Depth" so Bay 1 and 2 align at Depth 1; Bays 3 and 4 align at Depth 2
    #if (df["Bay_Num"] == 0 | df["Bay_Num" == 1]):
        #df["Bay_Depth"] = 0
    df['Bay_Depth'] = np.where(df['Bay_Num'] == 0, 0, (df['Bay_Num'] // 2) - 5)
    # Aggregate sales by the new physical coordinates
    physical_agg = df.groupby(['Aisle', 'Aisle_Row', 'Bay_Depth'])['LineCount'].sum().reset_index()

    # Split data into the two sides of the warehouse
    side1_df = physical_agg[physical_agg['Aisle'] <= 'I']
    side2_df = physical_agg[physical_agg['Aisle'] >= 'J']

    # Pivot both sides into 2D matrices
    matrix1 = side1_df.pivot(index='Bay_Depth', columns='Aisle_Row', values='LineCount').fillna(0)
    matrix2 = side2_df.pivot(index='Bay_Depth', columns='Aisle_Row', values='LineCount').fillna(0)

    # Sort Y-axis descending so Depth 1 (front of warehouse) is at the bottom
    matrix1 = matrix1.sort_index(ascending=False)
    matrix2 = matrix2.sort_index(ascending=False)

    # Ensure X-axis columns are sorted alphabetically (A Odd, A Even, B Odd, B Even...)
    matrix1 = matrix1[sorted(matrix1.columns)]
    matrix2 = matrix2[sorted(matrix2.columns)]

    # --- 4. Plotly Interactive Visualization (Subplots) ---
    # Create a 1x2 grid for the two sides of the warehouse
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("⬅️ Warehouse Side 1 (Aisles A - I)", "Warehouse Side 2 (Aisles J - Z) ➡️"),
        horizontal_spacing=0.05,  # Gap between the two sides
        shared_yaxes=True  # Lock the Y-axis so depths align visually
    )

    # Add Side 1 (A-I) Heatmap
    fig.add_trace(
        go.Heatmap(
            z=matrix1.values,
            x=matrix1.columns,
            y=matrix1.index,
            colorscale='YlOrRd',
            coloraxis="coloraxis",  # Share the color scale between both maps
            text=matrix1.values,  # Add values as text on hover/display
            texttemplate="%{text}",
            hovertemplate="Row: %{x}<br>Depth: %{y}<br>Line Count: %{z}<extra></extra>"
        ),
        row=1, col=1
    )

    # Add Side 2 (J-Z) Heatmap
    fig.add_trace(
        go.Heatmap(
            z=matrix2.values,
            x=matrix2.columns,
            y=matrix2.index,
            colorscale='YlOrRd',
            coloraxis="coloraxis",
            text=matrix2.values,
            texttemplate="%{text}",
            hovertemplate="Row: %{x}<br>Depth: %{y}<br>Line Count: %{z}<extra></extra>"
        ),
        row=1, col=2
    )

    # Formatting and layout updates
    fig.update_layout(
        height=800,
        coloraxis=dict(colorscale='YlOrRd', colorbar_title="Total Sales"),
        hovermode="closest",
        margin=dict(l=20, r=20, t=60, b=20)
    )

    # Move X-axes to the top for a floor plan feel
    fig.update_xaxes(side="bottom", tickangle=-45)

    # Label the Y-axes clearly
    fig.update_yaxes(title_text="Bay Depth (Distance into Aisle)", row=1, col=1)

    # Display the chart
    st.plotly_chart(fig, use_container_width=True)

    # --- 6. UPDATED FEATURE: Dynamic Sub-Heatmap Drill Down (with SKUs) ---
    st.markdown("---")
    st.header("🔍 Macro Drill-Down: Shelf & Bin Blueprint")
    st.markdown(
        "Pick a specific coordinate below to inspect exactly which **shelves (vertical levels)** and **bins (horizontal openings)** are selling.")

    # Selectboxes to let user target a location
    col1, col2 = st.columns(2)
    with col1:
        distinct_aisle_rows = sorted(df['Aisle_Row'].unique())
        selected_row = st.selectbox("🎯 Target Aisle & Row Side:", distinct_aisle_rows)
    with col2:
        row_filtered_df = df[df['Aisle_Row'] == selected_row]
        distinct_bays = sorted(row_filtered_df['Bay_Num'].unique())
        selected_bay = st.selectbox("🔢 Target Bay Number:", distinct_bays)

    # Filter data down to that exact physical zone using the Bay Number
    sub_df = df[(df['Aisle_Row'] == selected_row) & (df['Bay_Num'] == selected_bay)]

    if not sub_df.empty:
        # Group by Shelf and Bin, sum the Sales, AND combine the Item SKUs into a text string separated by line breaks (<br>)
        sub_agg = sub_df.groupby(['Shelf', 'Bin']).agg(
            Sales=('LineCount', 'sum'),
            Item_List=('Sku', lambda x: '<br>'.join(x.astype(str).unique()))
        ).reset_index()

        # Create TWO matrices: one for the math (Sales), and one for the text (SKUs)
        sub_matrix = sub_agg.pivot(index='Shelf', columns='Bin', values='Sales').fillna(0)
        item_matrix = sub_agg.pivot(index='Shelf', columns='Bin', values='Item_List').fillna("Empty Bin")

        # Sort both matrices identically so Shelf D is physically above Shelf A
        sub_matrix = sub_matrix.sort_index(ascending=False)
        sub_matrix = sub_matrix[sorted(sub_matrix.columns)]

        item_matrix = item_matrix.sort_index(ascending=False)
        item_matrix = item_matrix[sorted(item_matrix.columns)]

        # Build secondary heatmap using go.Heatmap to allow custom text injection
        sub_fig = go.Figure(data=go.Heatmap(
            z=sub_matrix.values,
            x=sub_matrix.columns,
            y=sub_matrix.index,
            colorscale='Viridis',
            text=sub_matrix.values,
            texttemplate="%{text}",
            customdata=item_matrix.values,  # Inject the SKU matrix in the background!
            hovertemplate=(
                "<b>Shelf:</b> %{y}<br>"
                "<b>Bin:</b> %{x}<br>"
                "<b>Line Count:</b> %{z}<br>"
                "---<br>"
                "<b>SKU(s) inside:</b><br>%{customdata}"
                "<extra></extra>"
            )
        ))

        sub_fig.update_layout(
            title=f"Detailed Micro-Map for {selected_row} | Bay: {selected_bay}",
            xaxis_title="Bin Number",
            yaxis_title="Shelf Level",
            height=350,
            margin=dict(l=20, r=20, t=50, b=20)
        )

        st.plotly_chart(sub_fig, use_container_width=True)
    else:
        st.warning("No sales inventory data registered at this specific coordinate.")

except Exception as e:
    st.error(
        f"Error processing data. Ensure your CSV locations are formatted 'A.10.B.03' and have numerical bays. Details: {e}")

# --- Calculate Aisle Distance Score ---
aisle_ascii = df['Aisle'].apply(ord)

# A through I: 'A' starts at 2, adding 2 for each letter
# J through Z: 'J' starts at 0, adding 2 for each letter
df['Aisle_Score'] = np.where(
    df['Aisle'] < 'J',
    (aisle_ascii - ord('A') + 1) * 3,
    (aisle_ascii - ord('J')) * 3
)

# --- Calculate Bay & Bin Horizontal Distance Score ---
# Ensure Bin is an integer (e.g., converting "03" to 3)
df['Bin_Num'] = pd.to_numeric(df['Bin'], errors='coerce').fillna(0).astype(int)

# Each Bay Depth is exactly 5 standard units. Then we add the Bin's position.
df['Bay_Bin_Score'] = (df['Bay_Depth'] * 5) + df['Bin_Num']

# --- Calculate Shelf Vertical Distance Score ---
# Find the absolute distance from Shelf 'C'
# ord('C') is 67. ord('A') is 65. abs(65 - 67) = 2.
# Create a safe function to calculate the shelf score
def get_shelf_score(val):
    try:
        # Convert to string, remove spaces, make uppercase, and grab the first letter
        clean_char = str(val).strip().upper()[0]
        return abs(ord(clean_char) - ord('C'))
    except:
        # If the shelf is missing entirely or completely broken, assign a penalty score of 5
        return 5

# Apply the safe function to the column
df['Shelf_Score'] = df['Shelf'].apply(get_shelf_score)

# --- Final Standardized Location Score ---
# Add them all together. Lower score means closer to the golden zone!
df['Location_Quality_Score'] = df['Aisle_Score'] + df['Bay_Bin_Score'] + df['Shelf_Score']

# --- 7. NEW FEATURE: Location Quality Map ---
st.markdown("---")
st.header("🎯 Warehouse Slotting Quality Map")
st.markdown(
    "This map visualizes your 'Distance from the Golden Zone'. **Green (Lower Score) is highly optimal**, while **Red (Higher Score) is inefficient**.")

# Aggregate the average quality score for each Bay from a top-down view
quality_agg = df.groupby(['Aisle', 'Aisle_Row', 'Bay_Depth'])['Location_Quality_Score'].mean().reset_index()

# Split into the two sides of the warehouse
q_side1_df = quality_agg[quality_agg['Aisle'] <= 'I']
q_side2_df = quality_agg[quality_agg['Aisle'] >= 'J']

# Pivot both sides into 2D matrices
q_matrix1 = q_side1_df.pivot(index='Bay_Depth', columns='Aisle_Row', values='Location_Quality_Score').fillna(
    0).sort_index(ascending=False)
q_matrix2 = q_side2_df.pivot(index='Bay_Depth', columns='Aisle_Row', values='Location_Quality_Score').fillna(
    0).sort_index(ascending=False)

q_matrix1 = q_matrix1[sorted(q_matrix1.columns)]
q_matrix2 = q_matrix2[sorted(q_matrix2.columns)]

# Create the Plotly figure (1x2 grid)
q_fig = make_subplots(
    rows=1, cols=2,
    subplot_titles=("⬅️ Quality: Side 1 (Aisles A - I)", "Quality: Side 2 (Aisles J - Z) ➡️"),
    horizontal_spacing=0.05, shared_yaxes=True
)

# Add Heatmaps using the Reversed Red-Yellow-Green scale
q_fig.add_trace(
    go.Heatmap(
        z=q_matrix1.values, x=q_matrix1.columns, y=q_matrix1.index,
        colorscale='RdYlGn_r', coloraxis="coloraxis2",
        text=q_matrix1.values, texttemplate="%{text:.1f}",
        hovertemplate="Row: %{x}<br>Depth: %{y}<br>Avg Quality: %{z:.1f}<extra></extra>"
    ), row=1, col=1
)

q_fig.add_trace(
    go.Heatmap(
        z=q_matrix2.values, x=q_matrix2.columns, y=q_matrix2.index,
        colorscale='RdYlGn_r', coloraxis="coloraxis2",
        text=q_matrix2.values, texttemplate="%{text:.1f}",
        hovertemplate="Row: %{x}<br>Depth: %{y}<br>Avg Quality: %{z:.1f}<extra></extra>"
    ), row=1, col=2
)

# Tweak layout so the colorbar has its own distinct scale (coloraxis2) separate from the Sales map
q_fig.update_layout(
    height=650,
    coloraxis2=dict(colorscale='RdYlGn_r', colorbar_title="Quality Score<br>(Lower = Better)"),
    margin=dict(l=20, r=20, t=60, b=20)
)

q_fig.update_xaxes(side="top", tickangle=-45)
q_fig.update_yaxes(title_text="Bay Depth", row=1, col=1)

st.plotly_chart(q_fig, use_container_width=True)

# --- 8. NEW FEATURE: Micro Drill-Down for Quality Scores ---
st.markdown("---")
st.header("🔬 Micro Drill-Down: Bin-by-Bin Quality Check")
st.markdown(
    "Inspect the exact mathematical distance score for every individual bin on a specific bay. **Green = Golden Zone, Red = Inefficient.**")

# Selectboxes to let user target a location for Quality
col1, col2 = st.columns(2)
with col1:
    # We can reuse the distinct_aisle_rows list from Step 6
    selected_row_q = st.selectbox("🎯 Target Aisle & Row Side (Quality):", distinct_aisle_rows, key="q_row")
with col2:
    row_filtered_df_q = df[df['Aisle_Row'] == selected_row_q]
    distinct_bays_q = sorted(row_filtered_df_q['Bay_Num'].unique())
    selected_bay_q = st.selectbox("🔢 Target Bay Number (Quality):", distinct_bays_q, key="q_bay")

# Filter data down to that exact physical zone using the Bay Number
sub_q_df = df[(df['Aisle_Row'] == selected_row_q) & (df['Bay_Num'] == selected_bay_q)]

if not sub_q_df.empty:
    # We use .mean() here, but since each bin only has 1 score, it just grabs the exact score
    sub_q_agg = sub_q_df.groupby(['Shelf', 'Bin'])['Location_Quality_Score'].mean().reset_index()
    sub_q_matrix = sub_q_agg.pivot(index='Shelf', columns='Bin', values='Location_Quality_Score').fillna(0)

    # Sort shelves descending so Shelf D is physically above Shelf A on screen
    sub_q_matrix = sub_q_matrix.sort_index(ascending=False)
    sub_q_matrix = sub_q_matrix[sorted(sub_q_matrix.columns)]

    # Build secondary quality heatmap
    sub_q_fig = px.imshow(
        sub_q_matrix,
        labels=dict(x="Bin Number", y="Shelf Level", color="Quality Score"),
        x=sub_q_matrix.columns,
        y=sub_q_matrix.index,
        text_auto=".0f",  # Show as clean, whole numbers
        color_continuous_scale="RdYlGn_r",  # Green = Good (Low Score), Red = Bad (High Score)
        aspect="auto"
    )

    sub_q_fig.update_layout(
        title=f"Bin-Level Quality Map for {selected_row_q} | Bay: {selected_bay_q}",
        height=350,
        margin=dict(l=20, r=20, t=50, b=20)
    )

    st.plotly_chart(sub_q_fig, use_container_width=True)
else:
    st.warning("No quality data registered at this specific coordinate.")