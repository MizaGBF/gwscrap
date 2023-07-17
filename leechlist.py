import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import math
import glob
import os

if __name__ == "__main__":
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

        if len(df) > 50: # for Players.csv or History.csv
            if filename.endswith('_Players.csv'):
                isplayerfile = True
                player_index = 16
            elif filename.endswith('_History.csv'):
                isplayerfile = True
                player_index = 18
            if len(df) > 300:
                df = df.head(300) # limit to 300 players
            part_count = int(math.ceil(len(df) / 50.0))
            
            index = 0
            parts = [df.iloc[:50]]
            for i in range(1, part_count):
                parts.append(df.iloc[50*i:min(len(df), 50*(i+1))])
                parts[-1].reset_index(drop=True, inplace=True) # reset index of subsequent parts
            df = pd.concat(parts, axis=1) # concatenate parts
        else:
            isplayerfile = False
            player_index = 16

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

        element_count = 0
        id_col = set()
        guild_col = set()
        name_col = set()
        best_col = set()
        # read first row
        for key, cell in table.get_celld().items():
            if key[0] != 0: continue
            cell_text = cell.get_text().get_text()
            if cell_text.endswith('.1') or cell_text.endswith('.2'):
                cell.get_text().set_text(cell_text[:-2])
            if cell_text == "id": id_col.add(key[1])
            elif cell_text == "guild": guild_col.add(key[1])
            elif cell_text == "name": name_col.add(key[1])
            elif cell_text == "best ranked" or cell_text == "best contrib.": best_col.add(key[1])

        # Set the font properties for each text object within the cells
        for key, cell in table.get_celld().items():
            cell.set_text_props(fontproperties=prop)
            cell.set_edgecolor('none')
            # Format float numbers as integers, with thousand separators
            cell_text = cell.get_text().get_text()
            if cell_text.replace(".", "").isnumeric():
                if key[1] in id_col: # ID formatting
                    cell.get_text().set_text(str(int(float(cell_text))))
                else:
                    cell.get_text().set_text('{:,}'.format(int(float(cell_text))))
                if key[1] == 0: # counting number of elements (first column)
                    element_count = max(element_count, int(cell.get_text().get_text()))
            if isplayerfile and (key[1] % player_index) == 0 and key[1] >= player_index and cell_text == "":
                empty_lines.add("{}-{}".format(key[0], key[1] // player_index))

        ldf = len(df) # data length
        for key, cell in table.get_celld().items():
            # Format other strings
            row_index, col_index = key
            if isplayerfile:
                col_part = col_index // player_index
                col_index = col_index % player_index
            cell_text = cell.get_text().get_text()
            if row_index == 0 and (col_index == 0 or (isplayerfile and col_index == 0)): # Hide the content of the first cell
                cell.get_text().set_text("")
            elif cell_text == "":
                if isplayerfile and "{}-{}".format(row_index, col_part) in empty_lines:
                    pass # do nothing
                elif row_index <= element_count:
                    cell.get_text().set_text("n/a")
            elif cell_text == "id":
                cell.get_text().set_text("ID")
            else:
                if col_index in guild_col and row_index > 0: # guild column
                    pass # no formatting
                elif col_index in best_col and row_index > 0: # best column (History.csv)
                    pass # no formatting
                elif col_index in name_col and row_index > 0: # name
                    pass # no formatting
                else:
                    cell.get_text().set_text(cell_text.capitalize().replace('& d', '& D'))

            # Alternating row colors
            if isplayerfile:
                row_index, col_index = key
                index = (row_index - 1) + (col_index // player_index) * (ldf + 1)
            else:
                index = row_index
            if row_index == 0: # header
                table[key].set_facecolor("#006600")
                table[key].get_text().set_color('#FFFFFF')
            elif row_index <= element_count:
                if (index + 1) % 2 == 1: # odd
                    cell_text = cell.get_text().get_text()
                    if col_index == 0 or (isplayerfile and (col_index % player_index) == 0): # first column
                        table[key].set_facecolor("#ffdeb3")
                    elif cell.get_text().get_text() == "n/a":
                        table[key].set_facecolor("#ffb3b3")
                    else:
                        table[key].set_facecolor("#ccffb3")
                else: # even
                    if col_index == 0 or (isplayerfile and (col_index % player_index) == 0): # first column
                        table[key].set_facecolor("#f7eee1")
                    elif cell.get_text().get_text() == "n/a":
                        table[key].set_facecolor("#f5d0d0")
                    else:
                        table[key].set_facecolor("#f6fff2")

        # Automatically adjust the cell size to fit the text
        table.auto_set_column_width(col=list(range(len(df.columns))))

        # Save the image
        plt.savefig(gw_name + '/' + filename.replace('.csv', '.png'), bbox_inches='tight')
        plt.close()
        print(filename.replace('.csv', '.png'), "done")