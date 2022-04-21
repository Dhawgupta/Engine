import os
import sys
import json
import argparse
import pickle
from seldonian.parse_tree import ParseTree
from seldonian.dataset import DataSetLoader
from seldonian.io_utils import dir_path


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	# Required args
	parser.add_argument('data_pth',  type=str,
		help='Path to data file')
	parser.add_argument('metadata_pth',  type=str,
		help='Path to metadata file')
	parser.add_argument('n_constraints',  type=int, default=1,help="Number of constraints")
	# Optional args
	parser.add_argument('--sensitive_column_names',  type=str,nargs="+",
		help="Sensitive column names (space-separated list)")
	parser.add_argument('--save_dir',  type=dir_path, default='.',
		help="Folder in which to save interface outputs")
	args = parser.parse_args()

	# Load metadata
	with open(args.metadata_pth,'r') as infile:
		metadata_dict = json.load(infile)
	print(metadata_dict)
	regime = metadata_dict['regime']
	print(regime)
	columns = metadata_dict['columns']

	if regime == 'supervised':
		sensitive_columns = metadata_dict['sensitive_columns']
		label_column = metadata_dict['label_column']
	elif regime == 'RL':
		sensitive_columns = []
		label_column = ''

	# Load dataset from file
	loader = DataSetLoader(
		column_names=columns,
		sensitive_column_names=sensitive_columns,
		label_column=label_column,
		regime=regime)

	ds = loader.from_csv(args.data_pth)
	
	# Save dataset object
	ds_save_dir = os.path.join(args.save_dir,'dataset.p')
	with open(ds_save_dir,'wb') as outfile:
		pickle.dump(ds,outfile,protocol=pickle.HIGHEST_PROTOCOL)
		print(f"Saved {ds_save_dir}\n")

	constraint_strs = ['-0.25 - J_pi_new'] 
	constraint_names = ['improved_J_pi_new']
	# constraint_strs = ['0.8 - min((PR | [M])/(PR | [F]),(PR | [F])/(PR | [M]))']
	deltas = [0.05]

	assert args.n_constraints == len(constraint_strs)
	# For each constraint, make a parse tree
	for ii in range(args.n_constraints):
		constraint_str = constraint_strs[ii]
		constraint_name = constraint_names[ii]

		delta = deltas[ii]
		# Create parse tree object
		parse_tree = ParseTree(delta=delta)

		# Fill out tree
		parse_tree.create_from_ast(constraint_str)
		# assign deltas for each base node
		# use equal weighting for each base node
		parse_tree.assign_deltas(weight_method='equal')

		# Assign bounds needed on the base nodes
		parse_tree.assign_bounds_needed()
		# Save parse tree

		pt_save_pth = os.path.join(args.save_dir,f'parse_tree_{constraint_name}.p')
		with open(pt_save_pth,'wb') as outfile:
			pickle.dump(parse_tree,outfile,protocol=pickle.HIGHEST_PROTOCOL)
			print(f"Saved {pt_save_pth}")

		# print(parse_tree.root.left.will_lower_bound)
		# print(parse_tree.root.left.will_upper_bound)
		# # # # Propagate bounds using random interval assignment to base variables
		# parse_tree.propagate_bounds(bound_method='manual')

		# # # Create the graphviz visualization and render it to a PDF
		title = f'Parse tree for expression:\n{constraint_str}\ndelta={delta}'
		graph = parse_tree.make_viz(title)
		graph.attr(fontsize='12')
		graph.view() # to open it as a pdf
