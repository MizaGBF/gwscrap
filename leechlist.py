import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import glob
import os

# Get csv list
csv_files = glob.glob("*.csv")

if len(csv_files) == 0: exit(0)

# make output folder
gw_name = csv_files[0].split('_')[0]
os.mkdir(gw_name)

for filename in csv_files:
    print("Opening", filename)
    # Load csv
    df = pd.read_csv(filename)

    # Limit to 100 players (for Players.csv)
    if filename.endswith('_Players.csv'):
        df = df.head(100)

    # Replace NaN values with an empty string
    df.replace(np.nan, '', inplace=True)

    # Load the font using FontManager
    prop = fm.FontProperties(fname='C:\\Windows\\Fonts\\INSTALL_THIS_UNICODE_FONT.ttf')

    # Create a figure and axis for plotting
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.axis('off')

    # Plot the table using ax.table()
    table = ax.table(cellText=df.values, colLabels=df.columns, cellLoc='left', loc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1, 1.5)

    # Set the font properties for each text object within the cells
    element_count = 0
    for key, cell in table.get_celld().items():
        cell.set_text_props(fontproperties=prop)
        cell.set_edgecolor('none')
        # Format float numbers as integers, with thousand separators
        cell_text = cell.get_text().get_text()
        if cell_text.replace(".", "").isnumeric():
            if key[1] == 2:
                cell.get_text().set_text(str(int(float(cell_text))))
            else:
                cell.get_text().set_text('{:,}'.format(int(float(cell_text))))
            if key[1] == 0: # counting number of elements (first column)
                element_count = max(element_count, int(cell.get_text().get_text()))

    # Format other strings
    for key, cell in table.get_celld().items():
        if (key[0] == 0 and key[1] == 0):
            continue
        cell_text = cell.get_text().get_text()
        if cell_text == "":
            if key[0] <= element_count:
                cell.get_text().set_text("n/a")
        elif cell_text == "id":
            cell.get_text().set_text("ID")
        else:
            if (key[1] == 3 and key[0] > 0 and key[0] <= element_count) or (key[1] == 3 and key[0] == element_count + 4): # don't touch names
                pass
            else:
                cell.get_text().set_text(cell_text.capitalize().replace('& d', '& D'))

    # Hide the content of the first cell
    table[0, 0].get_text().set_text("")

    # Alternating row colors
    for i, key in enumerate(table.get_celld().keys()):
        row_index, col_index = key
        if row_index == 0:
            table[key].set_facecolor("#006600")
            table[key].get_text().set_color('#FFFFFF')
        elif (row_index + 1) % 2 == 1 and row_index <= element_count:
            table[key].set_facecolor("#ccffb3")

    # Automatically adjust the cell size to fit the text
    table.auto_set_column_width(col=list(range(len(df.columns))))

    # Save the image
    plt.savefig(gw_name + '/' + filename.replace('.csv', '.png'), bbox_inches='tight')
    print(filename.replace('.csv', '.png'), "done")