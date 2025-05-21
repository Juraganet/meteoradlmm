# meteora_app/app.py
import streamlit as st
import pandas as pd
import numpy as np
from data_handler import fetch_meteora_pairs # Assuming data_handler.py is in the same directory

# --- Configuration ---
DYNAMIC_COLUMNS_TO_TRANSFORM = ['fee_tvl_ratio', 'fees', 'volume']
CURRENCY_COLUMNS = ['fees', 'volume', 'liquidity', 'trade_volume_24h']
PERCENTAGE_COLUMNS = ['apr', 'apy', 'fee_tvl_ratio', 'base_fee_percentage', 'max_fee_percentage']
OTHER_NUMERIC_COLUMNS = ['bin_step']
PRICE_COLUMNS = ['current_price']
MINT_COLUMNS = ['mint_x', 'mint_y', 'address']

DEFAULT_COLUMNS_TO_SHOW_CONFIG = [
    'name', 'mint_x', 'mint_y', 'fees', 'trade_volume_24h','volume', 'liquidity',
    'apr', 'fee_tvl_ratio', 'current_price', 'bin_step'
]
DEFAULT_COLUMNS_TO_SHOW_CONFIG = list(dict.fromkeys(DEFAULT_COLUMNS_TO_SHOW_CONFIG))

TIME_PERIODS = {
    "30 Min": "min_30", "1 Hour": "hour_1", "2 Hours": "hour_2",
    "4 Hours": "hour_4", "12 Hours": "hour_12", "24 Hours": "hour_24"
}
DEFAULT_TIME_PERIOD_LABEL = "24 Hours"

@st.cache_data(ttl=300)
def get_data_from_handler():
    try:
        df, total = fetch_meteora_pairs()
        cols_to_init_convert = [
            col for col in CURRENCY_COLUMNS + PERCENTAGE_COLUMNS + OTHER_NUMERIC_COLUMNS + PRICE_COLUMNS
            if col in df.columns and col not in DYNAMIC_COLUMNS_TO_TRANSFORM
        ]
        for col in cols_to_init_convert:
            if not pd.api.types.is_numeric_dtype(df[col]):
                df[col] = pd.to_numeric(df[col], errors='coerce')
        return df, total
    except Exception as e:
        st.error("Failed to load data from the API. Please check server logs or try again later.")
        print(f"ERROR in get_data_from_handler: {e}")
        return pd.DataFrame(), 0

st.set_page_config(layout="wide")
st.title("Meteora DLMM Pair Data Viewer")

# --- Sidebar Inputs ---
st.sidebar.header("Time Period for Stats")
time_period_labels = list(TIME_PERIODS.keys())
try:
    default_period_index = time_period_labels.index(DEFAULT_TIME_PERIOD_LABEL)
except ValueError:
    default_period_index = 0
selected_time_period_label = st.sidebar.selectbox(
    "Select Period:", options=time_period_labels, index=default_period_index
)
selected_time_period_api_key = TIME_PERIODS[selected_time_period_label]
st.sidebar.caption(f"Stats for: {selected_time_period_label}")

st.sidebar.header("Custom Metric & Filters")
target_liquidity_for_fees_calc = st.sidebar.number_input(
    label="Target Liquidity for Fee Metric ($)",
    min_value=1, value=1000, step=100, key="target_liq_input_for_calc"
)
min_liquidity_threshold = st.sidebar.number_input(
    label="Minimum Liquidity to Display ($)",
    min_value=0, value=5000, step=1000, key="min_liq_threshold",
    help="Pairs with liquidity below this value will be hidden. Set to 0 to show all."
)
# --- End Sidebar Inputs ---

df_raw, total_pairs_api = get_data_from_handler()

if df_raw.empty:
    if not any(getattr(m, 'type', None) == 'error' for m in st.get_option("global.displayable_messages")):
        st.info("No pair data is currently available to display.")
else:
    df_processed = df_raw.copy()

    for col_name in DYNAMIC_COLUMNS_TO_TRANSFORM:
        if col_name in df_processed.columns:
            df_processed[col_name] = df_processed[col_name].apply(
                lambda data_dict: data_dict.get(selected_time_period_api_key) if isinstance(data_dict, dict) else np.nan
            )

    # Consolidate numeric conversion
    all_cols_to_ensure_numeric = list(set(CURRENCY_COLUMNS + PERCENTAGE_COLUMNS + OTHER_NUMERIC_COLUMNS + PRICE_COLUMNS))
    current_currency_columns = CURRENCY_COLUMNS[:] # Local copy for modification

    for col in all_cols_to_ensure_numeric:
        if col in df_processed.columns:
            if not pd.api.types.is_numeric_dtype(df_processed[col]):
                df_processed[col] = pd.to_numeric(df_processed[col], errors='coerce')
            if not pd.api.types.is_numeric_dtype(df_processed[col]):
                print(f"DEVELOPER WARNING: Column '{col}' could not be converted to a numeric type (current dtype: {df_processed[col].dtype}).")

    # --- Calculate Custom Column ---
    custom_fees_col_name_dynamic = f"fees_per_${int(target_liquidity_for_fees_calc)}_liq"
    
    if 'fees' in df_processed.columns and 'liquidity' in df_processed.columns and \
       pd.api.types.is_numeric_dtype(df_processed['fees']) and \
       pd.api.types.is_numeric_dtype(df_processed['liquidity']):
        
        if target_liquidity_for_fees_calc <= 0:
            df_processed[custom_fees_col_name_dynamic] = np.nan
        else:
            condition_for_calc = (
                (df_processed['liquidity'] >= target_liquidity_for_fees_calc) &
                (df_processed['liquidity'] != 0) &
                pd.notna(df_processed['liquidity']) & pd.notna(df_processed['fees'])
            )
            df_processed[custom_fees_col_name_dynamic] = np.where(
                condition_for_calc,
                (df_processed['fees'] * target_liquidity_for_fees_calc) / df_processed['liquidity'], np.nan
            )
    else:
        df_processed[custom_fees_col_name_dynamic] = np.nan
    
    if custom_fees_col_name_dynamic not in current_currency_columns:
        current_currency_columns.append(custom_fees_col_name_dynamic)
    if custom_fees_col_name_dynamic not in all_cols_to_ensure_numeric and custom_fees_col_name_dynamic in df_processed.columns and pd.api.types.is_numeric_dtype(df_processed[custom_fees_col_name_dynamic]):
        all_cols_to_ensure_numeric.append(custom_fees_col_name_dynamic) # Ensure it's treated as numeric if calculated
    # --- End Calculate Custom Column ---

    # --- Apply Liquidity Filter ---
    if 'liquidity' in df_processed.columns and pd.api.types.is_numeric_dtype(df_processed['liquidity']):
        if min_liquidity_threshold > 0:
            # Keep rows where liquidity is greater than or equal to the threshold, or where liquidity is NaN (to not drop them if they had other valid data)
            # If you want to strictly drop rows with NaN liquidity as well when a filter is active, remove `| df_processed['liquidity'].isna()`
            df_processed = df_processed[
                (df_processed['liquidity'] >= min_liquidity_threshold) | (df_processed['liquidity'].isna())
            ]
    # --- End Apply Liquidity Filter ---


    st.write(f"Displaying {len(df_processed)} of ~{total_pairs_api} available pairs (after filters) for '{selected_time_period_label}'.")

    all_available_cols = df_processed.columns.tolist()
    
    current_default_config = DEFAULT_COLUMNS_TO_SHOW_CONFIG[:]
    if custom_fees_col_name_dynamic in all_available_cols: # Ensure dynamic col is in options
        try:
            liq_idx = current_default_config.index('liquidity')
            if custom_fees_col_name_dynamic not in current_default_config:
                current_default_config.insert(liq_idx + 1, custom_fees_col_name_dynamic)
        except ValueError:
            if custom_fees_col_name_dynamic not in current_default_config:
                current_default_config.append(custom_fees_col_name_dynamic)
    
    actual_defaults_to_show = [col for col in current_default_config if col in all_available_cols]
    if not actual_defaults_to_show and all_available_cols:
        actual_defaults_to_show = all_available_cols[:min(len(all_available_cols), 7)]

    st.sidebar.header("Display Options")
    selected_columns = st.sidebar.multiselect(
        "Select columns to display:", options=all_available_cols, default=actual_defaults_to_show
    )

    if not selected_columns:
        st.warning("Please select at least one column to display the table.")
    elif df_processed.empty and min_liquidity_threshold > 0 : # Check if df_processed is empty *after* filtering
        st.info(f"No pairs found with liquidity of at least ${min_liquidity_threshold:,.0f}.")
    else:
        df_display = df_processed[selected_columns].copy()

        if custom_fees_col_name_dynamic in df_display.columns and 'liquidity' in df_display.columns:
            current_display_cols = df_display.columns.tolist()
            try:
                liq_idx_display = current_display_cols.index('liquidity')
                if custom_fees_col_name_dynamic in current_display_cols:
                    current_display_cols.pop(current_display_cols.index(custom_fees_col_name_dynamic))
                current_display_cols.insert(liq_idx_display + 1, custom_fees_col_name_dynamic)
                df_display = df_display[current_display_cols]
            except ValueError:
                pass

        st.header("Pair Data")

        column_config = {}
        for col_name in df_display.columns:
            label_text = col_name.replace("_", " ").title()
            if col_name == custom_fees_col_name_dynamic:
                formatted_target_liq = f"${int(target_liquidity_for_fees_calc):,.0f}"
                label_text = f"Fees per {formatted_target_liq} Liq"

            is_numeric_col = pd.api.types.is_numeric_dtype(df_display[col_name])

            if col_name in current_currency_columns:
                if is_numeric_col: column_config[col_name] = st.column_config.NumberColumn(label=label_text, format="dollar")
                else: column_config[col_name] = st.column_config.TextColumn(label=label_text)
            elif col_name in PERCENTAGE_COLUMNS:
                if is_numeric_col: column_config[col_name] = st.column_config.NumberColumn(label=label_text, format="%.2f%%")
                else: column_config[col_name] = st.column_config.TextColumn(label=label_text)
            elif col_name in PRICE_COLUMNS:
                 if is_numeric_col: column_config[col_name] = st.column_config.NumberColumn(label=label_text, format="%.12f")
                 else: column_config[col_name] = st.column_config.TextColumn(label=label_text)
            elif col_name in OTHER_NUMERIC_COLUMNS:
                 if is_numeric_col:
                    if df_display[col_name].dropna().apply(lambda x: x == int(x) if pd.notna(x) else True).all():
                         column_config[col_name] = st.column_config.NumberColumn(label=label_text, format="%d")
                    else: column_config[col_name] = st.column_config.NumberColumn(label=label_text, format="plain")
                 else: column_config[col_name] = st.column_config.TextColumn(label=label_text)
            elif col_name in MINT_COLUMNS:
                column_config[col_name] = st.column_config.TextColumn(label=label_text, width="small")
            elif col_name not in current_currency_columns + PERCENTAGE_COLUMNS + PRICE_COLUMNS + OTHER_NUMERIC_COLUMNS + MINT_COLUMNS:
                column_config[col_name] = st.column_config.TextColumn(label=label_text)

        if not df_display.empty:
            st.dataframe(
                df_display, use_container_width=True, column_config=column_config, hide_index=True
            )
        elif selected_columns: # This case is now less likely if df_processed was empty and handled above
             st.info("No data matches the current selection criteria or filters.")