import os
import re
import json
import argparse
import xml.etree.ElementTree as ElementTree

def clone_grid(grid):
	return [
		[cell for cell in row]
		for row in grid
	]

def clone_empty_grid(grid):
	return [
		[False for cell in row]
		for row in grid
	]

def convert_array_to_grid(items, x, y):
	rows = [
		items[x * i:x * (i + 1)]
		for i in range(y)
	]
	rows.reverse()

	return  [
		[cell != '0' for cell in row]
		for row in rows
	]

def parse_byte_grid(bytes, x, y):
	bytes = [
		bit
		for byte in bytes.split(' ')
		for bit in bin(int(byte))[2:].rjust(8, '0')[::-1]
	]
	return convert_array_to_grid(bytes, x, y)

def parse_double_value_grid(values, x, y):
	values = values.split(' ')[1::2]
	return convert_array_to_grid(values, x, y)

def make_grid_outline(buildable_grid):
	grid = clone_empty_grid(buildable_grid)

	for i in range(len(buildable_grid)):
		for j in range(len(buildable_grid[i])):
			if buildable_grid[i][j]:
				for k in range(-1, 2):
					for l in range(-1, 2):
						if buildable_grid[i + k][j + l] is False:
							grid[i + k][j + l] = True
	return grid

def subtract(from_grid, grid):
	final_grid = clone_grid(from_grid)
	for i in range(len(from_grid)):
		for j in range(len(from_grid[i])):
			if grid[i][j]:
				final_grid[i][j] = False
	return final_grid

def print_grid(grid, max_width=236):
	for row in grid:
		print(''.join(['X' if cell else ' ' for cell in row[0:max_width]]))

def blocker_generator(x, y):
	return {
		'Identifier': 'BlockTile_1x1',
		'Label': '',
		'Position': f'{x},{y}',
		'Size': '1,1',
		'Icon': None,
		'Template': 'Blocker',
		'Color': {
			'A': 255,
			'R': 0,
			'G': 0,
			'B': 0
		},
		'Borderless': True,
		'Road': False,
		'Radius': 0.0,
		'InfluenceRange': -2,
		'PavedStreet': False,
		'BlockedAreaLength': 0,
		'BlockedAreaWidth': 0,
		'Direction': 'Up'
	}

def serialize_grid(filename, grid, object_generator=blocker_generator):
	layout = {
		'FileVersion': 4,
		'LayoutVersion': '1.0.0.0',
		'Objects': [
			object_generator(j, i)
			for i in range(len(grid))
			for j in range(len(grid[i]))
			if grid[i][j]
		]
	}

	with open(filename, 'w+') as file:
		json.dump(layout, file)

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('gamefile', help='XML interpreted from A7M\'s gamedata.data file')
	parser.add_argument('-o', '--outputFile', help='Path to output AnnoDesigner layout file')
	args = parser.parse_args()

	with open(args.gamefile, encoding='utf-8') as gamedata_file:
		unescaped_gamedata_file = re.sub(r'&#([a-zA-Z0-9]+);?', r'[#\1;]', gamedata_file.read())
	gamedata = ElementTree.fromstring(unescaped_gamedata_file)
	island_width = int(gamedata.findtext('./GameSessionManager/AreaIDs/x', '0'))
	island_height = int(gamedata.findtext('./GameSessionManager/AreaIDs/y', '0'))
	river_width = int(gamedata.findtext('./GameSessionManager/WorldManager/RiverGrid/x', '0'))
	river_height = int(gamedata.findtext('./GameSessionManager/WorldManager/RiverGrid/y', '0'))

	if island_width != river_width or island_height != river_height:
		raise Exception()

	island_values = gamedata.findtext('./GameSessionManager/AreaIDs/val')
	river_bytes = gamedata.findtext('./GameSessionManager/WorldManager/RiverGrid/bits')

	island_grid = parse_double_value_grid(island_values, island_width, island_height)
	river_grid = parse_byte_grid(river_bytes, river_width, river_height)

	grid = subtract(island_grid, river_grid)
	grid_outline = make_grid_outline(grid)

	#print_grid(grid_outline)

	output = args.outputFile or f'{os.path.splitext(args.gamefile)[0]}.ad'
	serialize_grid(output, grid_outline)
