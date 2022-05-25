import os, pickle
import autograd.numpy as np   # Thinly-wrapped version of Numpy
import pandas as pd
from functools import partial

class CandidateSelection(object):
	""" 
	Object for running candidate selection
	
	Attributes
	----------
	model : models.SeldonianModel class instance
		The Seldonian model object 
	candidate_dataset : dataset.Dataset class instance
		The dataset object containing candidate data
	n_safety: int
		The length of the safety dataset, used 
		when calculating confidence bounds

	parse_trees: List(parse_tree.ParseTree objects)
		List of parse tree objects containing the 
		behavioral constraints

	primary_objective: models.SeldonianModel method
		The objective function that would be solely optimized 
		in the absence of behavioral constraints, i.e. the
		loss function

	optimization_technique: str
		The method for optimization during candidate
		selection. E.g. 'gradient_descent', 'barrier_function'

	optimizer: str
		The string name of the optimizer used 
		during candidate selection
	
	initial_solution: numpy ndarray
		The model weights used to initialize the optimizer

	regime
		The type of machine learning algorithm,
		e.g. supervised or RL

	write_logfile: bool
		Whether to write outputs of candidate selection 
		to disk

	Methods
	-------
	run()
		Run candidate selection

	objective_with_barrier(theta)
		The objective function to be optimized if 
		minimization_technique == 'barrier'
		given model weights, theta
	
	evaluate_primary_objective(theta)
		Get value of the primary objective given model weights,
		theta. Wrapper for self.primary_objective where 
		data is fixed. Used as input to gradient descent

	get_constraint_upper_bound(theta)
		Get value of the upper bound of the constraint function. 
		Used as input to gradient descent.


	"""
	def __init__(self,
		model,
		candidate_dataset,
		n_safety,
		parse_trees,
		primary_objective,
		optimization_technique='barrier_function',
		optimizer='Powell',
		initial_solution=None,
		regime='supervised',
		write_logfile=False,
		**kwargs):
		self.regime = regime
		self.model = model
		self.candidate_dataset = candidate_dataset
		self.n_safety = n_safety
		if self.regime == 'supervised':
			# To get the initial solution we may need to do a model fit
			# For that reason we need the data in fittable form

			# Separate features from label
			label_column = candidate_dataset.label_column
			self.labels = self.candidate_dataset.df[label_column]
			self.features = self.candidate_dataset.df.loc[:,
				self.candidate_dataset.df.columns != label_column]

			if not candidate_dataset.include_sensitive_columns:
				self.features = self.features.drop(
					columns=self.candidate_dataset.sensitive_column_names)
		
			if candidate_dataset.include_intercept_term:
				self.features.insert(0,'offset',1.0) # inserts a column of 1's
		
		self.parse_trees = parse_trees
		self.primary_objective = primary_objective # must accept theta, features, labels
		self.optimization_technique = optimization_technique
		self.optimizer = optimizer
		self.initial_solution = initial_solution
		self.candidate_solution = None
		self.write_logfile = write_logfile
		
		if 'reg_coef' in kwargs:
			self.reg_coef = kwargs['reg_coef']

		if self.regime == 'RL':
			self.gamma = kwargs['gamma']
			self.min_return = kwargs['min_return']
			self.max_return = kwargs['max_return']

	def run(self,**kwargs):

		if self.optimization_technique == 'gradient_descent':
			from seldonian.optimizers.gradient_descent import gradient_descent_adam

			gd_kwargs = dict(
				primary_objective=self.evaluate_primary_objective,
				upper_bound_function=self.get_constraint_upper_bound,
				alpha_theta=kwargs['alpha_theta'],
			    alpha_lamb=kwargs['alpha_lamb'],
			    beta_velocity=kwargs['beta_velocity'],
			    beta_rmsprop=kwargs['beta_rmsprop'],
			    num_iters=kwargs['num_iters'],
				theta_init=self.initial_solution,
				store_values=self.write_logfile,
				verbose=kwargs['verbose'],
				parse_trees=self.parse_trees,
			)

			# If user specified the gradient of the primary
			# objective, then pass it here

			if 'use_primary_gradient' in kwargs:
				if kwargs['use_primary_gradient']==True:
					if self.regime == 'supervised':

						# need to know name of primary objective first
						primary_objective_name = self.primary_objective.__name__
						grad_primary_objective = getattr(self.model,
							f'gradient_{primary_objective_name}')
						# Now fix the features and labels so that the function 
						# is only a function of theta
						
						grad_primary_objective_theta = partial(
							grad_primary_objective,
							X=self.features.values,Y=self.labels.values)
						gd_kwargs['primary_gradient'] = grad_primary_objective_theta
					else:
						raise NotImplementedError(
							"Using a provided primary objective gradient"
							" is not yet supported for regimes other"
							" than supervised learning")

			res = gradient_descent_adam(**gd_kwargs
				)

			if self.write_logfile:
				log_counter = 0
				logdir = os.path.join(os.getcwd(),
					'logs')
				os.makedirs(logdir,exist_ok=True)
				filename = os.path.join(logdir,
					f'candidate_selection_log{log_counter}.p')

				while os.path.exists(filename):
					filename = filename.replace(
						f'log{log_counter}',f'log{log_counter+1}')
					log_counter+=1
				with open(filename,'wb') as outfile:
					pickle.dump(res,outfile)
					print(f"Wrote {filename} with candidate selection log info")

			if res['solution_found']:
				print("Found solution to gradient descent")
				candidate_solution = res['candidate_solution']
			else:
				print("No solution found!")
				candidate_solution = 'NSF'

		elif self.optimization_technique == 'barrier_function':
			if self.optimizer in ['Powell','CG','Nelder-Mead','BFGS']:
				
				from scipy.optimize import minimize 
				res = minimize(
					self.objective_with_barrier,
					x0=self.initial_solution,
					method=self.optimizer,
					options=kwargs['minimizer_options'], 
					args=())
				
				candidate_solution=res.x

			elif self.optimizer == 'CMA-ES':
				# from seldonian.cmaes import minimize
				import cma

				es = cma.CMAEvolutionStrategy(self.initial_solution, 0.2,
					kwargs['minimizer_options'])
				
				es.optimize(self.objective_with_barrier)
				candidate_solution=es.result.xbest
				
				raise NotImplementedError(
					f"Optimizer {self.optimizer} is not supported")
		else:
			raise NotImplementedError(f"Optimization technique: {self.optimization_technique} is not implemented")

		# Reset parse tree base node dicts, 
		# including data and datasize attributes
		for pt in self.parse_trees:
			pt.reset_base_node_dict(reset_data=True)

		# Unset data and datasize on base nodes
		# Return the candidate solution we believe will pass the safety test
		return candidate_solution
		
	def objective_with_barrier(self,theta):

		# Get the primary objective evaluated at the given theta
		# and the entire candidate dataset
		if self.regime == 'supervised':
			result = self.primary_objective(self.model, theta, 
				self.features, self.labels)

		elif self.regime == 'RL':
			# Want to maximize the importance weight so minimize negative importance weight
			result = -1.0*self.primary_objective(self.model,theta,
				self.candidate_dataset)

			# Optionally adding regularization term so that large thetas
			# make this less negative
			# and therefore worse 
			if hasattr(self,'reg_coef'):
				reg_term = self.reg_coef*np.linalg.norm(theta)
				result += reg_term

		# Prediction of what the safety test will return. 
		# Initialized to pass
		predictSafetyTest = True     
		for tree_i,pt in enumerate(self.parse_trees): 
			# before we propagate, reset the bounds on all base nodes
			pt.reset_base_node_dict()

			bounds_kwargs = dict(
				theta=theta,
				dataset=self.candidate_dataset,
				model=self.model,
				bound_method='ttest',
				branch='candidate_selection',
				n_safety=self.n_safety,
				regime=self.regime)

			if self.regime == 'RL':
				bounds_kwargs['gamma'] = self.gamma
				bounds_kwargs['min_return'] = self.min_return
				bounds_kwargs['max_return'] = self.max_return


			pt.propagate_bounds(**bounds_kwargs)
			
			# Check if the i-th behavioral constraint is satisfied
			upper_bound = pt.root.upper 
			
			if upper_bound > 0.0: # If the current constraint was not satisfied, the safety test failed
				# If up until now all previous constraints passed,
				# then we need to predict that the test will fail
				# and potentially add a penalty to the objective
				if predictSafetyTest:
					# Set this flag to indicate that we don't think the safety test will pass
					predictSafetyTest = False  

					# Put a barrier in the objective. Any solution 
					# that we think will fail the safety test 
					# will have a large cost associated with it
					if self.optimization_technique == 'barrier_function':
						# print("here")
						result = 100000.0    
				# Add a shaping to the objective function that will 
				# push the search toward solutions that will pass 
				# the prediction of the safety test

				result = result + upper_bound
		
		# graph = pt.make_viz(title)
		# graph.attr(fontsize='12')
		# graph.view() # to open it as a pdf
		# input("End of optimzer iteration")
		return result

	def evaluate_primary_objective(self,theta):
		# Get value of the primary objective given model weights
		if self.regime == 'supervised':
			result = self.primary_objective(self.model, theta, 
					self.features.values, self.labels.values)
			return result

		elif self.regime == 'RL':
			# Want to maximize the importance weight so minimize negative importance weight
			# Adding regularization term so that large thetas make this less negative
			# and therefore worse 
			result = -1.0*self.primary_objective(self.model,theta,
				self.candidate_dataset)

			if hasattr(self,'reg_coef'):
				reg_term = self.reg_coef*np.linalg.norm(theta)
				result += reg_term
			return result

	def get_constraint_upper_bound(self,theta):
		pt = self.parse_trees[0]
		pt.reset_base_node_dict()

		bounds_kwargs = dict(
			theta=theta,
			dataset=self.candidate_dataset,
			model=self.model,
			bound_method='ttest',
			branch='candidate_selection',
			n_safety=self.n_safety,
			regime=self.regime
			)

		if self.regime == 'RL':
			bounds_kwargs['gamma'] = self.gamma
			bounds_kwargs['min_return'] = self.min_return
			bounds_kwargs['max_return'] = self.max_return

		pt.propagate_bounds(**bounds_kwargs)

		return pt.root.upper