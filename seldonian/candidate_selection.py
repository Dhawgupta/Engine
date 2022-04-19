import numpy as np


class CandidateSelection(object):
	def __init__(self,
		model,
		candidate_dataset,
		n_safety,
		parse_trees,
		primary_objective,
		optimization_technique='barrier_function',
		optimizer='Powell',
		initial_solution_fn=None,
		**kwargs):
		self.model = model
		self.candidate_dataset = candidate_dataset
		self.n_safety = n_safety
		# Separate features from label
		label_column = candidate_dataset.label_column
		self.labels = self.candidate_dataset.df[label_column]
		self.features = self.candidate_dataset.df.loc[:,
			self.candidate_dataset.df.columns != label_column]
		self.features = self.features.drop(
			columns=self.candidate_dataset.sensitive_column_names)
		self.features.insert(0,'offset',1.0) # inserts a column of 1's
		self.parse_trees = parse_trees
		self.primary_objective = primary_objective # must accept theta, features, labels
		self.optimization_technique = optimization_technique
		self.optimizer = optimizer
		self.initial_solution_fn = initial_solution_fn
		self.candidate_solution = None

	def run(self,**kwargs):

		# default initial solution function is leastsq
		if not self.initial_solution_fn:
			initial_solution = self.model.fit(
				self.features, self.labels)
		else:
			initial_solution = self.initial_solution_fn(
				self.features, self.labels)
		# prin
		# print("initial solution is:",initial_solution)
		if self.optimizer in ['Powell','CG','Nelder-Mead','BFGS',]:
			from scipy.optimize import minimize 
			res = minimize(
				self.candidate_objective,
				x0=initial_solution,
				method=self.optimizer,
				options=kwargs['minimizer_options'], 
				args=())
			
			candidate_solution=res.x

		elif self.optimizer == 'CMA-ES':
			# from src.cmaes import minimize
			import cma
			n_iters=1000
			options = {'tolfun':1e-14, 'maxiter':n_iters}

			es = cma.CMAEvolutionStrategy(initial_solution, 0.5,options)
			# es = cma.CMAEvolutionStrategy(np.zeros_like(initial_solution), 0.5,options)
			
			es.optimize(self.candidate_objective)
			# print(es.result_pretty())
			candidate_solution=es.result.xbest
			# 
			# N=self.features.shape[1]

			# candidate_solution = minimize(N=N,
			# 	# lamb=int(4+np.floor(3*np.log(N))),
			# 	lamb=20,
			# 	initial_solution=np.zeros_like(initial_solution),
			# 	objective=self.candidate_objective)
		else:
			raise NotImplementedError(
				f"Optimizer {self.optimizer} is not supported")
		# Reset parse tree base node dicts, 
		# including data and datasize attributes
		for pt in self.parse_trees:
			pt.reset_base_node_dict(reset_data=True)
		# print(candidate_solution)

		# Unset data and datasize on base nodes
		# Return the candidate solution we believe will pass the safety test
		return candidate_solution

	def candidate_objective(self,theta):
		# Get the primary objective evaluated at the given theta
		# and the entire candidate dataset
		# print("theta is:", theta)
		result = self.primary_objective(self.model, theta, 
			self.features, self.labels)
		# print("Primary objective eval is:", result)
		# Prediction of what the safety test will return. 
		# Initialized to pass
		predictSafetyTest = True     
		for tree_i,pt in enumerate(self.parse_trees): 
			# before we propagate, reset the bounds on all base nodes
			pt.reset_base_node_dict()

			pt.propagate_bounds(
				theta=theta,
				dataset=self.candidate_dataset,
				model=self.model,
				bound_method='ttest',
				branch='candidate_selection',
				n_safety=self.n_safety)

			# Check if the i-th behavioral constraint is satisfied
			upper_bound = pt.root.upper  
			if self.optimization_technique == 'barrier_function':
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

						result = 100000.0    

					# Add a shaping to the objective function that will 
					# push the search toward solutions that will pass 
					# the prediction of the safety test
					result = result + upper_bound
		# print(result)
		
		# title = f'Parse tree'
		# graph = pt.make_viz(title)
		# graph.attr(fontsize='12')
		# graph.view() # to open it as a pdf
		# input("End of optimzer iteration")
		return result
