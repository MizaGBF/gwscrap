import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import math
import glob
import os

# Get csv list
csv_files = glob.glob("*.csv")

if len(csv_files) == 0: exit(0)

# make output folder
gw_name = csv_files[0].split('_')[0]
try: os.mkdir(gw_name)
except: pass

# Load the font using FontManager
prop = fm.FontProperties(fname='C:\\Windows\\Fonts\\INSTALL_THIS_UNICODE_FONT.ttf')

for filename in csv_files:
    print("Opening", filename)
    # Load csv
    df = pd.read_csv(filename)

    # (for Players.csv)
    isplayerfile = (filename.endswith('_Players.csv') and len(df) > 50)
    if isplayerfile:
        if len(df) > 300:
            df = df.head(300) # limit to 300 players
        part_count = int(math.ceil(len(df) / 50.0))
        
        index = 0
        parts = [df.iloc[:50]]
        for i in range(1, part_count):
            parts.append(df.iloc[50*i:min(len(df), 50*(i+1))])
            parts[-1].reset_index(drop=True, inplace=True) # reset index of subsequent parts
        df = pd.concat(parts, axis=1) # concatenate parts

    # Replace NaN values with an empty string
    df.replace(np.nan, '', inplace=True)

    # Create a figure and axis for plotting
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.axis('off')

    # Plot the table using ax.table()
    table = ax.table(cellText=df.values, colLabels=df.columns, cellLoc='left', loc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1, 1.5)

    empty_lines = set() # for player files

    # Set the font properties for each text object within the cells
    element_count = 0
    for key, cell in table.get_celld().items():
        cell.set_text_props(fontproperties=prop)
        cell.set_edgecolor('none')
        # Format float numbers as integers, with thousand separators
        cell_text = cell.get_text().get_text()
        if cell_text.replace(".", "").isnumeric():
            if key[1] == 2 or (isplayerfile and (key[1] % 16) == 2): # ID formatting
                cell.get_text().set_text(str(int(float(cell_text))))
            else:
                cell.get_text().set_text('{:,}'.format(int(float(cell_text))))
            if key[1] == 0: # counting number of elements (first column)
                element_count = max(element_count, int(cell.get_text().get_text()))
        if isplayerfile and (key[1] % 16) == 0 and key[1] >= 16 and cell_text == "":
            empty_lines.add("{}-{}".format(key[0], key[1] // 16))

    # Format other strings
    for key, cell in table.get_celld().items():
        row_index, col_index = key
        if (row_index == 0 and col_index == 0):
            continue
        if isplayerfile:
            col_part = col_index // 16
            col_index = col_index % 16
        cell_text = cell.get_text().get_text()
        if cell_text == "":
            if isplayerfile and "{}-{}".format(row_index, col_part) in empty_lines:
                pass
            elif row_index <= element_count:
                cell.get_text().set_text("n/a")
        elif isplayerfile and cell_text == "Unnamed: 0":
            cell.get_text().set_text("")
        elif cell_text == "id":
            cell.get_text().set_text("ID")
        else:
            if (col_index == 3 and row_index > 0 and row_index <= element_count) or (col_index == 3 and row_index == element_count + 4) or (filename.endswith('_Players.csv') and col_index == 4 and row_index > 0 and row_index <= element_count): # don't touch names
                pass
            else:
                cell.get_text().set_text(cell_text.capitalize().replace('& d', '& D'))

    # Hide the content of the first cell
    table[0, 0].get_text().set_text("")

    # Alternating row colors
    ldf = len(df)
    for i, key in enumerate(table.get_celld().keys()):
        row_index, col_index = key
        if isplayerfile: index = (row_index - 1) + (col_index // 16) * (ldf + 1)
        else: index = row_index
        if row_index == 0: # header
            table[key].set_facecolor("#006600")
            table[key].get_text().set_color('#FFFFFF')
        elif (index + 1) % 2 == 1 and row_index <= element_count: # odd
            if col_index == 0 or (isplayerfile and (col_index % 16) == 0):
                table[key].set_facecolor("#ffdeb3")
            else:
                table[key].set_facecolor("#ccffb3")
        elif (index + 1) % 2 == 0 and row_index <= element_count: # even
            if col_index == 0 or (isplayerfile and (col_index % 16) == 0):
                table[key].set_facecolor("#f7eee1")
            else:
                table[key].set_facecolor("#f6fff2")

    # Automatically adjust the cell size to fit the text
    table.auto_set_column_width(col=list(range(len(df.columns))))

    # Save the image
    plt.savefig(gw_name + '/' + filename.replace('.csv', '.png'), bbox_inches='tight')
    plt.close()
    print(filename.replace('.csv', '.png'), "done")