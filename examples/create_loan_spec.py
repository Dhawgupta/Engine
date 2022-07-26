import os
from seldonian.parse_tree.parse_tree import ParseTree
from seldonian.dataset import DataSetLoader
from seldonian.utils.io_utils import dir_path,load_json,save_pickle
from seldonian.spec import SupervisedSpec
from seldonian.models.models import *

if __name__ == '__main__':
	data_pth = "../static/datasets/supervised/german_credit/german_loan_numeric_forseldonian.csv"
	metadata_pth = "../static/datasets/supervised/german_credit/metadata_german_loan.json"
	save_dir = '.'
	# Load metadata
	metadata_dict = load_json(metadata_pth)

	regime = metadata_dict['regime']
	columns = metadata_dict['columns']
	sensitive_columns = metadata_dict['sensitive_columns']
	sub_regime = metadata_dict['sub_regime']
	label_column = metadata_dict['label_column']
	
	model_class = LogisticRegressionModel
	
	primary_objective = model_class().sample_logistic_loss

	# Load dataset from file
	loader = DataSetLoader(
		regime=regime)

	dataset = loader.load_supervised_dataset(
		filename=data_pth,
		metadata_filename=metadata_pth,
		include_sensitive_columns=False,
		include_intercept_term=True,
		file_type='csv')
	
	constraint_strs = ['abs((PR | [M]) - (PR | [F])) - 0.15'] 
	
	deltas = [0.05]

	# For each constraint, make a parse tree
	parse_trees = []
	for ii in range(len(constraint_strs)):
		constraint_str = constraint_strs[ii]

		delta = deltas[ii]
		# Create parse tree object
		parse_tree = ParseTree(delta=delta,regime='supervised',
			sub_regime='classification',columns=columns)

		# Fill out tree
		parse_tree.build_tree(
			constraint_str=constraint_str,
			delta_weight_method='equal')
		
		parse_trees.append(parse_tree)

	# Save spec object, using defaults where necessary
	spec = SupervisedSpec(
		dataset=dataset,
		model_class=model_class,
		frac_data_in_safety=0.6,
		primary_objective=primary_objective,
		parse_trees=parse_trees,
		initial_solution_fn=model_class().fit,
		use_builtin_primary_gradient_fn=True,
		bound_method='ttest',
		optimization_technique='gradient_descent',
		optimizer='adam',
		optimization_hyperparams={
			'lambda_init'   : 0.5,
		    'alpha_theta'   : 0.01,
		    'alpha_lamb'    : 0.01,
		    'beta_velocity' : 0.9,
		    'beta_rmsprop'  : 0.95,
		    'num_iters'     : 1000,
		    'gradient_library': "autograd",
		    'hyper_search'  : None,
		    'verbose'       : True,
		}
	)

	spec_save_name = os.path.join(save_dir,'spec.pkl')
	save_pickle(spec_save_name,spec)
	print(f"Saved Spec object to: {spec_save_name}")
