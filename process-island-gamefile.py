import os
import re
import json
import argparse
from xml.etree import ElementTree
from xml.etree.ElementTree import Element

LAND_BLOCKER = 'L'
COASTLINE_BLOCKER = 'C'
HARBOUR_BLOCKER = 'H'

## Grid operations

def clone_grid(grid):
	return [
		[cell for cell in row]
		for row in grid
	]

def clone_empty_grid(grid, default_value=False):
	return [
		[default_value for cell in row]
		for row in grid
	]

def create_empty_grid(width, height, default_value=False):
	return [
		[default_value for __ in range(width)]
		for _ in range(height)
	]

def copy_grid(from_grid, to_grid, x, y):
	"""
	Copies "from_grid" to "to_grid" at starting position "x", "y" (in the "to_grid")
	"""
	for j, row in enumerate(from_grid):
		for i, value in enumerate(row):
			to_grid[j + y][i + x] = value

def outline(input_grid):
	"""
	Returns grid which has tiles which outlines input grid.
	"""
	output_grid = clone_empty_grid(input_grid)

	for i in range(len(input_grid)):
		for j in range(len(input_grid[i])):
			if input_grid[i][j]:
				for k in range(-1, 2):
					for l in range(-1, 2):
						if input_grid[i + k][j + l] is False:
							output_grid[i + k][j + l] = True
	return output_grid

def set_grid_values(input_grid, value):
	"""
	Positions where "grid" has a value are set to "value".
	"""
	output_grid = clone_grid(input_grid)
	for i in range(len(input_grid)):
		for j in range(len(input_grid[i])):
			if input_grid[i][j]:
				output_grid[i][j] = value
	return output_grid

def overlay(input_grid, *grids):
	"""
	Positions where "input_grid" doesn't have a value, the first value from "grids" on same position is set.
	"""
	assert len(grids) > 0
	output_grid = clone_grid(input_grid)
	for i in range(len(output_grid)):
		for j in range(len(output_grid[i])):
			if not input_grid[i][j]:
				for grid in grids:
					if grid[i][j]:
						output_grid[i][j] = grid[i][j]
						break
	return output_grid

def subtract(from_grid, grid):
	final_grid = clone_grid(from_grid)
	for i in range(len(from_grid)):
		for j in range(len(from_grid[i])):
			if grid[i][j]:
				final_grid[i][j] = False
	return final_grid

def intersect(*grids):
	assert len(grids) > 0
	output_grid = clone_empty_grid(grids[0])
	for i in range(len(output_grid)):
		for j in range(len(output_grid[i])):
			if all((grid[i][j] for grid in grids)):
				output_grid[i][j] = True
	return output_grid

## Parsing grids

def convert_array_to_grid(items, width, height):
	rows = [
		items[width * i:width * (i + 1)]
		for i in range(height)
	]
	rows.reverse()

	return  [
		[cell != '0' for cell in row]
		for row in rows
	]

def parse_byte_grid(bytes, width, height):
	bytes = [
		bit
		for byte in bytes.split(' ')
		for bit in bin(int(byte))[2:].rjust(8, '0')[::-1]
	]
	return convert_array_to_grid(bytes, width, height)

def parse_value_grid(values, width, height):
	values = values.split(' ')
	return convert_array_to_grid(values, width, height)

def parse_double_value_grid(values, width, height):
	values = values.split(' ')[1::2]
	return convert_array_to_grid(values, width, height)

def parse_island_grid(area_ids_node: Element):
	width = int(area_ids_node.findtext('./x'))
	height = int(area_ids_node.findtext('./y'))

	if area_ids_node.findtext('./SparseEnabled') == '1':
		blocks = area_ids_node.findall('./block')
		sub_grid_width, sub_grid_height = 0, 0
		buildable_grid = create_empty_grid(width, height)
		for block in blocks:
			mode = block.findtext('./mode')
			if mode == '1':
				# start - set width/height
				sub_grid_width = int(block.findtext('./x'))
				sub_grid_height = int(block.findtext('./y'))
			elif mode == '0':
				# end
				sub_grid_width = 0
				sub_grid_height = 0
			elif mode is None:
				# individual subgrid values
				assert sub_grid_width > 0 and sub_grid_height > 0, 'Subgrid size is expected to be set'
				x = int(block.findtext('./x') or 0)
				y = int(block.findtext('./y') or 0)
				sub_grid = parse_double_value_grid(block.findtext('./values'), sub_grid_width, sub_grid_height)
				copy_grid(sub_grid, buildable_grid, x, y, )
			elif mode == '2':
				# entire subgrid has same values
				assert sub_grid_width > 0 and sub_grid_height > 0, 'Subgrid size is expected to be set'
				x = int(block.findtext('./x') or 0)
				y = int(block.findtext('./y') or 0)
				value = parse_double_value_grid(block.findtext('./default'), 1, 1)[0][0]
				sub_grid = create_empty_grid(sub_grid_width, sub_grid_height, value)
				copy_grid(sub_grid, buildable_grid, x, y)
		return buildable_grid
	else:
		return parse_double_value_grid(area_ids_node.findtext('./val'), width, height)

def parse_river_grid(river_grid_node: Element):
	width = int(river_grid_node.findtext('./x'))
	height = int(river_grid_node.findtext('./y'))
	return parse_byte_grid(river_grid_node.findtext('./bits'), width, height)

def parse_land_grid(water_grid_node: Element):
	width = int(water_grid_node.findtext('./x'))
	height = int(water_grid_node.findtext('./y'))
	return parse_byte_grid(water_grid_node.findtext('./bits'), width, height)

## Verb handlers

def extract():
	with open(ARGS.gamefile, encoding='utf-8') as gamedata_file:
		unescaped_gamedata_file = re.sub(r'&#([a-zA-Z0-9]+);?', r'[#\1;]', gamedata_file.read())
	gamedata = ElementTree.fromstring(unescaped_gamedata_file)

	island_grid = parse_island_grid(gamedata.find('./GameSessionManager/AreaIDs'))
	river_grid = parse_river_grid(gamedata.find('./GameSessionManager/WorldManager/RiverGrid'))
	not_water_grid = parse_land_grid(gamedata.find('./GameSessionManager/WorldManager/Water'))
	land_grid = subtract(intersect(island_grid, not_water_grid), river_grid)
	harbour_grid = subtract(island_grid, not_water_grid)

	# handle nouns
	if ARGS.noun == 'island-grid':
		grid = island_grid
	elif ARGS.noun == 'land-grid':
		grid = land_grid
	elif ARGS.noun == 'river-grid':
		grid = river_grid
	elif ARGS.noun == 'harbour-grid':
		grid = harbour_grid
	elif ARGS.noun == 'island-outline':
		outlined_land_grid = outline(land_grid)
		coastline_grid = intersect(outlined_land_grid, harbour_grid)
		outlined_harbour_grid = outline(subtract(harbour_grid, outlined_land_grid))
	
		grid = clone_empty_grid(land_grid)
		grid = overlay(
			grid,
			set_grid_values(coastline_grid, COASTLINE_BLOCKER),
			set_grid_values(outlined_land_grid, LAND_BLOCKER),
			set_grid_values(outlined_harbour_grid, HARBOUR_BLOCKER)
		)
	else:
		print(f'Unknown noun "{ARGS.noun}"')
		return

	targets = {
		'to-ad-layout': to_ad_layout,
		'to-screen': to_screen
	}
	targets[ARGS.target](grid)

## Target handlers

def blocker_generator(x, y, color):
	return {
		'Identifier': 'BlockTile_1x1',
		'Label': '',
		'Position': f'{x},{y}',
		'Size': '1,1',
		'Icon': None,
		'Template': 'Blocker',
		'Color': color,
		'Borderless': True,
		'Road': False,
		'Radius': 0.0,
		'InfluenceRange': -2,
		'PavedStreet': False,
		'BlockedAreaLength': 0,
		'BlockedAreaWidth': 0,
		'Direction': 'Up'
	}

def land_blocker(x, y):
	return blocker_generator(x, y, {
		'A': 255,
		'R': 0,
		'G': 0,
		'B': 0
	})
def coastline_blocker(x, y):
	return blocker_generator(x, y, {
		'A': 255,
		'R': 30,
		'G': 144,
		'B': 255
	})
def harbour_blocker(x, y):
	return blocker_generator(x, y, {
		'A': 255,
		'R': 192,
		'G': 192,
		'B': 192
	})

def to_ad_layout(grid):
	filename = ARGS.outputFile or f'{os.path.splitext(ARGS.gamefile)[0]}.ad'

	if not ARGS.overwrite and os.path.exists(filename):
		print('Output file already exists, specify -y to overwrite it')
		return

	blockers = {
		True: land_blocker,
		LAND_BLOCKER: land_blocker,
		COASTLINE_BLOCKER: coastline_blocker,
		HARBOUR_BLOCKER: harbour_blocker,
	}
	
	layout = {
		'FileVersion': 4,
		'LayoutVersion': '1.0.0.0',
		'Objects': [
			blockers[grid[i][j]](j, i)
			for i in range(len(grid))
			for j in range(len(grid[i]))
			if grid[i][j]
		]
	}

	with open(filename, 'w') as file:
		json.dump(layout, file)

def to_screen(grid):
	max_width = os.get_terminal_size().columns
	characters = {
		True: '\u2588',
		False: ' '
	}
	for row in grid:
		print(''.join([characters.get(cell, str(cell)) for cell in row[0:max_width]]))

## Parsing command line arguments

def add_targets(noun_parser: argparse.ArgumentParser, *, to_screen=False, to_ad_layout=False):
	target_parser = noun_parser.add_subparsers(dest='target', required=True)
	if to_screen:
		add_to_screen_target(target_parser)
	if to_ad_layout:
		add_to_ad_layout_target(target_parser)

def add_to_screen_target(parser: argparse._SubParsersAction):
	parser.add_parser('to-screen')

def add_to_ad_layout_target(parser: argparse._SubParsersAction):
	to_ad_layout_parser = parser.add_parser('to-ad-layout')
	to_ad_layout_parser.add_argument('-o', '--outputFile', help='Path to output AnnoDesigner layout file')
	to_ad_layout_parser.add_argument('-y', '--overwrite', help='Overwrites output file if exists')

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	verb_parsers = parser.add_subparsers(dest='verb', required=True)
	extract_parser = verb_parsers.add_parser('extract')
	extract_parser.add_argument('gamefile', help='XML interpreted from A7M\'s gamedata.data file')

	noun_parsers = extract_parser.add_subparsers(dest='noun', required=True)
	add_targets(
		noun_parsers.add_parser('island-grid', help='Land, rivers and harbour areas'),
		to_screen=True
	)
	add_targets(
		noun_parsers.add_parser('land-grid', help='Land areas'),
		to_screen=True
	)
	add_targets(
		noun_parsers.add_parser('river-grid', help='River areas'),
		to_screen=True
	)
	add_targets(
		noun_parsers.add_parser('harbour-grid', help='Harbour areas'),
		to_screen=True
	)
	add_targets(
		noun_parsers.add_parser('island-outline', help='River areas'),
		to_screen=True, to_ad_layout=True
	)

	ARGS = parser.parse_args()

	verbs = {
		'extract': extract
	}
	verbs[ARGS.verb]()
