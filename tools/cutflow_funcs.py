'''A list of functions for manipulating cutflows.
1. Text files --> cutflow strings
    - `parse_Scott_cutflow_file()` extracts cutflow strings in Scott's format from a file.
    - ` parse_ZdZdPP_cutflow_file()` extracts cutflow strings in the ZdZdPostProcessing format from a file.
2. Cutflow strings --> DFs
    - `str_to_df_Scott()` creates a DF from a cutflow string in Scott's format.
    - `str_to_df_ZdZdPP()` creates a DF from a cutflow string in the ZdZdPostProcessing format.
3. Manipulating cutflow DFs
    - `simplify_ZdZdPP_cutflow()` edits ZdZdPostProcessing DFs
4. DF --> spreadsheet
    - `make_spreadsheet()` converts multiple DFs to a spreadsheet of multiple sheets.

Questions:
- What is a cutflow?
    - A cutflow is a table of cuts on a dataset, where each row is a cut that reduces (or occasionally has no effect on the number of events.)
'''

def test_func():
    return 2.1

import numpy as np
import pandas as pd
import re

# ----------------------------------------- #
# 1. Extracting cutflow strings from a file #
# ----------------------------------------- #
# Different functions are created for the different cutflow formats

# 1.1 Scott's format
def parse_Scott_cutflow_file(filepath):
    """Look for cutflows in Scott's format in a file and extract them.
    Header example: zd5_23a --- reco
    Return a dictionary of 'cutflow name: cutflow string' pairs."""
    # Open file and extract lines
    with open(filepath, 'r') as f:
        content = f.read()
    lines = content.split('\n')
    
    cutflow_dict = {}
    current_key = None
    current_lines = []    
    for line in lines:
        # Check if this line is a header (contains " --- ")
        if ' --- ' in line and not line.startswith('|'):
            # Save the previous cutflow if it exists
            if current_key is not None:
                cutflow_dict[current_key] = '\n'.join(current_lines).strip()
            # Start a new cutflow
            current_key = line.strip()
            current_lines = []
        else:
            # Add line to current cutflow
            current_lines.append(line)
    # Don't forget to save the last cutflow
    if current_key is not None:
        cutflow_dict[current_key] = '\n'.join(current_lines).strip()
    
    return cutflow_dict

# 1.2 ZdZdPostProcessing format
def parse_ZdZdPP_cutflow_file(filepath):
    """Look for cutflows in the ZdZdPostProcessing format in a file and extract them.
    Header example: mc23a_zd5
    Return a dictionary of 'cutflow header: cutflow string' pairs."""
    # Open file and extract lines
    with open(filepath, 'r') as f:
        content = f.read()
    lines = content.split('\n')
    
    cutflow_dict = {}
    current_key = None
    current_lines = []
    for line in lines:
        # Check if this line is a header (doesn't start with | or -)
        # and is not empty
        if line.strip() and not line.startswith('|') and not line.startswith('-'):
            # Save the previous cutflow if it exists
            if current_key is not None:
                cutflow_dict[current_key] = '\n'.join(current_lines).strip()
            # Start a new cutflow
            current_key = line.strip()
            current_lines = []
        else:
            # Add line to current cutflow
            current_lines.append(line)
    # Don't forget to save the last cutflow
    if current_key is not None:
        cutflow_dict[current_key] = '\n'.join(current_lines).strip()
    
    return cutflow_dict

# ------------------------------------------- #
# 2. Converting cutflow strings to DataFrames #
# ------------------------------------------- #
# Different functions are created for the different cutflow formats

# 2.2 Scott's format
def str_to_df_Scott(cutflow_str):
    '''Create a DF from a string of a cutflow table in Scott's format.'''
    lines = cutflow_str.strip().split('\n')
    data = []
    for line in lines[2:]:  # Skip the first two header lines
        parts = line.split('|')[1:-1]  # Split by '|' and ignore empty parts
        row = [part.strip() for part in parts]
        data.append(row)
    columns = ['Cut', 'events_4e', 'weights_4e', 'events_2e2m', 'weights_2e2m', 'events_4m', 'weights_4m', 'events_All', 'weights_All']
    df = pd.DataFrame(data, columns=columns)
    # Reorder columns
    new_col_order = ['Cut', 'weights_4e', 'events_4e', 'weights_2e2m', 'events_2e2m', 'weights_4m', 'events_4m', 'weights_All', 'events_All']
    df = df[new_col_order]
    return df

# 2.2 ZdZdPostProcessing format
def str_to_df_ZdZdPP(cutflow_str):
    '''Create a DF from a string of a cutflow table in the ZdZdPostProcessing format.'''
    lines = [line.strip() for line in cutflow_str.strip().split('\n') if line.strip() and not line.strip().startswith('-')]
    # Parse header
    header_parts = re.findall(r'\|([^|]+)', lines[0])
    header = ['Cuts'] + [col.strip() for col in header_parts[1:]]
    # Parse data rows
    data = []
    for line in lines[1:]:
        cols = [col.strip() for col in re.findall(r'\|([^|]+)', line)]
        data.append(cols)
    df = pd.DataFrame(data, columns=header)
    
    # Split columns (except 'Cuts') into weights and events
    new_cols = {}
    new_cols['Cuts'] = df['Cuts']
    for col in df.columns[1:]:
        # Extract float (weight) and integer (events)
        weights = df[col].str.extract(r'([0-9.]+)\s*\(')[0].astype(float)
        events = df[col].str.extract(r'\(([0-9]+)\)')[0].astype(int)
        
        new_cols[f'{col}_weights'] = weights
        new_cols[f'{col}_events'] = events
    
    return pd.DataFrame(new_cols)

# ---------------------------------- #
# 3. Manipulating cutflow dataframes #
# ---------------------------------- #

def simplify_Scott_cutflow(df):
    # Find the index of the row where the value of 'Cut' is '*AS SR1*'
    index = df[df['Cut'] == '*AS SR1*'].index
    # Keep only the rows up to and including that index
    df = df.loc[:index[0]]
    # Remove rows where 'Cut' contains certain values
    simplified_df = df[~df['Cut'].str.contains('overlap|jetclean|tight|\*', case=False, regex=True)]\
        .reset_index(drop=True, inplace=False)#[new_col_order]

    return simplified_df

def simplify_ZdZdPP_cutflow(df, drop=None):
    # Make a column which contains the sum of each column that has 'events' in the name, for each row. This will be the 'all' column.
    df['weights_All'] = df.loc[:, df.columns.str.contains('weights')].sum(axis=1)
    df['events_All'] = df.loc[:, df.columns.str.contains('events')].sum(axis=1)
    # Drop the 2nd and 3rd columns (which are the first 'events' and 'weights' columns)
    df_simplified = df.copy().drop(columns=[df.columns[2]])
    df_simplified = df_simplified.copy().drop(columns=[df_simplified.columns[1]])
    # Rename columns to 4e, 2e2m, 4m
    new_columns = []
    for col in df_simplified.columns:
        if col.split('_')[0][-1] == '1':
            new_columns.append(f'{col.split("_")[1]}_4e')
        elif col.split('_')[0][-1] == '2':
            new_columns.append(f'{col.split("_")[1]}_2e2m')
        elif col.split('_')[0][-1] == '3':
            new_columns.append(f'{col.split("_")[1]}_4m')
        else:
            new_columns.append(col)
    df_simplified.columns = new_columns
    # Optional: drop columns containing a certain word (e.g. 'weights')
    if drop is not None:
        df_simplified = df_simplified.drop(columns=[col for col in df_simplified.columns if drop in col])
    
    return df_simplified

# def rename_cols_ZdZdPP(df):

# ------------------------------------------------------ #
# 4. Making spreadsheet from multiple cutflow DataFrames #
# ------------------------------------------------------ #

def make_spreadsheet(outfile, table_dict):
    '''Take in a filename and a dictionary with format: {sheet_name: table_df}
    Save as an excel file with each table in its own sheet.'''
    with pd.ExcelWriter(outfile) as writer:
        for sheet_name, table_df in table_dict.items():
            df = table_df
            df.to_excel(writer, sheet_name=sheet_name, index=False)

# Example use:
# make_spreadsheet('my_out_file.xlsx', {'my sheet': str_to_df(my_cutflow_str), })
