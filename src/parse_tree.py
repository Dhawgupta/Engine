import ast
import graphviz
import numpy as np
from src.nodes import *

class ParseTree(object):
	""" 
	Class to represent a parse tree for a single behavioral constraint

	Attributes
	----------
	name : root
		Root node which contains the whole tree 
		via left and right attributes.
		Gets assigned when tree is built
	delta: float
		Confidence level. Specifies the maximum probability 
		that the algorithm can return a solution violates the
		behavioral constraint.
	n_nodes: int
		Total number of nodes in the parse tree
	n_base_nodes: int
		Number of base variable nodes in the parse tree.
		Does not include constants.
	base_node_dict: dict
		Keeps track of base variable nodes,
		their confidence bounds and whether 
		the bounds have been calculated
		for a given base node already.
		Helpful for handling case where we have 
		duplicate base nodes 
	node_fontsize: int
		Fontsize used in nodes displayed with graphviz 

	Methods
	-------
	create_from_ast(s)
		Create the node structure of the tree
		given a mathematical string expression, s

	_ast_tree_helper(root)
		Helper function for create_from_ast()

	_ast2pt_node(ast_node)
		Mapper between python's ast library's
		node objects to our node objects

	assign_deltas(weight_method)
		Assign the delta values to the base nodes in the tree

	_assign_deltas_helper(node,weight_method)
		Helper function for assign_deltas()

	propagate_bounds(bound_method='ttest')
		Traverse the parse tree, calculate confidence
		bounds on base nodes and 
		then propagate bounds using propagation logic

	_propagator_helper(node,bound_method)
		Helper function for propagate_bounds()

	_protect_nan(bound,bound_type)
		Handle nan as negative infinity if in lower bound
		and postitive infinity if in upper bound 

	_propagate(node)
		Given an internal node, calculate 
		the propagated confidence interval
		from its children using the 
		node's operator type

	add(a,b)
		Add intervals a and b

	sub(a,b)
		Subtract intervals a and b

	mult(a,b)
		Multiply intervals a and b

	div(a,b)
		Divide intervals a and b    

	abs(a)
		Take the absolute value of interval a 

	exp(a)
		Calculate e raised to the interval a 

	make_viz(title)
		Make a graphviz graph object of 
		the parse tree and give it a title

	make_viz_helper(root,graph)
		Helper function for make_viz()

	"""
	def __init__(self,delta):
		self.root = None 
		self.delta = delta
		self.n_nodes = 0
		self.n_base_nodes = 0
		self.base_node_dict = {} 
		self.node_fontsize = 12

	def create_from_ast(self,s):
		""" 
		Create the node structure of the tree
		given a mathematical string expression, s

		Parameters
		----------
		s : str
			mathematical expression written in Python syntax
			from which we build the parse tree
		"""
		self.node_index = 0

		tree = ast.parse(s)
		# makes sure this is a single expression
		assert len(tree.body) == 1 

		expr = tree.body[0]
		root = expr.value

		# Recursively build the tree
		self.root = self._ast_tree_helper(root)

	def _ast_tree_helper(self,node):
		""" 
		From a given node in the ast tree,
		make a node in our tree and recurse
		to children of this node.

		Attributes
		----------
		node : ast.AST node class instance 
			
		"""
		# base case
		if node is None:
			return None

		# make a new node object
		new_node,is_leaf = self._ast2pt_node(node)

		if new_node.node_type == 'base_node':
			self.n_base_nodes += 1

			# strip out conditional columns and parentheses
			node_name_isolated = new_node.name.split(
				"|")[0].strip().strip('(').strip()
			if node_name_isolated in measure_functions:
				new_node.measure_function_name = node_name_isolated		

			# if node with this name not already in self.base_node_dict
			# then make a new entry 
			if new_node.name not in self.base_node_dict:
				# 
				self.base_node_dict[new_node.name] = {
					'computed':False,
					'lower':float('-inf'),
					'upper':float('inf'),
					'data_dict':None,
					'datasize':0
				}

		self.n_nodes += 1
		new_node.index = self.node_index
		self.node_index +=1

		# If node is a leaf node, don't check for children
		if is_leaf:
			return new_node

		if hasattr(node,'left'):
			new_node.left = self._ast_tree_helper(node.left)
		if hasattr(node,'right'):
			new_node.right = self._ast_tree_helper(node.right)
		if hasattr(node,'args') and node.func.id not in measure_functions:
			if len(node.args) == 0 or len(node.args) > 2: 
				readable_args = [x.id for x in node.args]
				raise NotImplementedError(
					"Please check the syntax of the function: "
				   f" {new_node.name}(), with arguments: {readable_args}")
			for ii,arg in enumerate(node.args):
				if ii == 0:
					new_node.left = self._ast_tree_helper(arg)
				if ii == 1:
					new_node.right = self._ast_tree_helper(arg)

		return new_node

	def _ast2pt_node(self,ast_node):
		""" 
		Mapper to convert ast.AST node objects
		to our Node() objects

		Parameters
		----------
		ast_node : ast.AST node class instance
		"""
		is_leaf = False
		kwargs = {}

		if isinstance(ast_node,ast.BinOp):
			# +,-,*,/,** operators
			if ast_node.op.__class__ == ast.BitOr:
				# BitOr is used for "Function | [Y]" i.e. 
				# "Function given conditional column Y" 
				node_class = BaseNode
				try: 
					conditional_columns = [x.id for x in ast_node.right.elts]
				except:
					raise RuntimeError(
						"An issue was found when parsing"
						" your conditional expression.\n"
						"The issue is most likely due to"
						" missing or mismatched parentheses. ")
				# node_name = ast_node.left.id
				node_name = '(' + ' | '.join([ast_node.left.id,str(conditional_columns)]) + ')'
				is_leaf = True
				return node_class(node_name,
					conditional_columns=conditional_columns),is_leaf
			else:
				node_class = InternalNode
				try:
					node_name = op_mapper[ast_node.op.__class__]
				except KeyError:
					op = not_supported_op_mapper[ast_node.op.__class__]
					raise NotImplementedError("Error parsing your expression."
						" An operator was used which we do not support: "
					   f"{op}")
				return node_class(node_name),is_leaf

		elif isinstance(ast_node,ast.Name):
			# named quantity like "e", "Mean_Squared_Error"
			# If variable name is "e" then make it a constant, not a base variable
			if ast_node.id == 'e':
				node_name = 'e'
				node_class = ConstantNode
				node_value = np.e
				is_leaf = True
				return node_class(node_name,node_value),is_leaf
			else:	
				if ast_node.id not in measure_functions:
					raise NotImplementedError("Error parsing your expression."
						" A variable name was used which we do not recognize: "
					   f"{ast_node.id}")
				node_class = BaseNode
				node_name = ast_node.id
				is_leaf = True
				return node_class(node_name),is_leaf

		elif isinstance(ast_node,ast.Constant):
			# A constant floating point or integer number
			node_class = ConstantNode
			node_value = ast_node.value
			node_name = str(node_value)
			is_leaf = True
			return node_class(node_name,node_value),is_leaf

		elif isinstance(ast_node,ast.Call):
			# a function call like abs(arg1), min(arg1,arg2), FPR()
			node_class = InternalNode
			node_name = ast_node.func.id

		return node_class(node_name),is_leaf

	def create_from_ghat_str(self,s,**kwargs):
		""" 
		Create the node structure of the tree
		given a custom string expression
		for ghat, s

		Parameters
		----------
		s : str
			mathematical expression written in Python syntax
			from which we build the parse tree
		"""
		self.root = CustomBaseNode(name=s,**kwargs)
		self.root.index = 0
		self.n_nodes = 1
		self.n_base_nodes = 1
		self.base_node_dict[self.root.name] = {
					'computed':False,
					'lower':float('-inf'),
					'upper':float('inf'),
					'data_dict':None,
					'datasize':0
				}

	def assign_deltas(self,weight_method='equal',**kwargs):
		""" 
		Assign the delta values to the base nodes in the tree.

		Parameters
		----------
		weight_method : str
			How you want to assign the deltas to the base nodes
			'equal' : split up delta equally among base nodes 
		"""
		assert self.n_nodes > 0, "Number of nodes must be > 0"
		self._assign_deltas_helper(self.root,weight_method,**kwargs)
		
	def _assign_deltas_helper(self,node,weight_method,**kwargs):
		""" 
		Helper function to traverse the parse tree 
		and assign delta values to base nodes.
		--TODO-- 
		Currently uses preorder, but there is likely
		a faster way to do this because if you get 
		to a base node, you know none 
		of its parents are possible base nodes

		Parameters
		----------
		weight_method : str
			How you want to assign the deltas to the base nodes
				'equal' : split up delta equally among base nodes 
		"""
		
		if not node:
			return

		if isinstance(node,BaseNode): # captures all child classes of BaseNode as well
			if weight_method == 'equal':
				node.delta = self.delta/self.n_base_nodes

		self._assign_deltas_helper(node.left,weight_method)
		self._assign_deltas_helper(node.right,weight_method)
		return

	def propagate_bounds(self,
		**kwargs):
		""" 
		Postorder traverse (left, right, root)
		through the tree and calculate confidence
		bounds on base nodes using a specified bound_method,
		then propagate bounds using propagation logic

		Parameters
		----------
		bound_method : str
			The method for calculating confidence bounds 
				'ttest' : Student's t test
		"""

		if not self.root:
			return []

		self._propagator_helper(self.root,
			**kwargs)
	
	def _propagator_helper(self,node,
		**kwargs):
		""" 
		Helper function for traversing 
		through the tree and propagating confidence bounds

		Parameters
		----------
		bound_method : str
			The method for calculating confidence bounds 
				'ttest' : Student's t test
		"""

		# if we hit a constant node or run past the end of the tree
		# return because we don't need to calculate bounds
		if not node or isinstance(node,ConstantNode):
			return 

		# if we hit a BaseNode,
		# then calculate confidence bounds and return 
		if isinstance(node,BaseNode):
			# Check if bound has already been calculated for this node name
			# If so, use precalculated bound
			if self.base_node_dict[node.name]['computed'] == True:
				node.lower = self.base_node_dict[node.name]['lower']
				node.upper = self.base_node_dict[node.name]['upper'] 
				return
			else:
				if 'dataset' in kwargs:
					# Check if data has already been prepared
					# for this node name. If so, use precalculated data
					if self.base_node_dict[node.name]['data_dict']!=None:
						# print("Data precalculated for bound")
						data_dict = self.base_node_dict[node.name]['data_dict']
						datasize = self.base_node_dict[node.name]['datasize']
					else:
						# print("calculating data for bound")
						data_dict,datasize = node.calculate_data_forbound(
							**kwargs)
						self.base_node_dict[node.name]['data_dict'] = data_dict
						self.base_node_dict[node.name]['datasize'] = datasize

					kwargs['data_dict'] = data_dict
					kwargs['datasize'] = datasize

				node.lower,node.upper = node.calculate_bounds(
					**kwargs)
				self.base_node_dict[node.name]['computed'] = True
				self.base_node_dict[node.name]['lower'] = node.lower
				self.base_node_dict[node.name]['upper'] = node.upper
			return 
		
		# traverse to children first
		self._propagator_helper(node.left,
			**kwargs)
		self._propagator_helper(node.right,
			**kwargs)
		
		# Here we must be at an internal node and therefore need to propagate
		node.lower,node.upper = self._propagate(node)
	
	def _protect_nan(self,bound,bound_type):
		""" 
		Handle nan as negative infinity if in lower bound
		and postitive infinity if in upper bound 

		Parameters
		----------
		bound : float
			Upper or lower bound 
		bound_type : str
			'lower' or 'upper'
		"""
		if np.isnan(bound):
			if bound_type == 'lower':
				return float('-inf')
			if bound_type == 'upper':
				return float('inf')
		else:
			return bound

	def _propagate(self,node):
		"""
		Helper function for propagating confidence bounds

		Parameters
		----------
		node : Node() class instance
		"""
		if node.name == 'add':
			a = (node.left.lower,node.left.upper)
			b = (node.right.lower,node.right.upper)
			return self._add(a,b)
			
		if node.name == 'sub':
			a = (node.left.lower,node.left.upper)
			b = (node.right.lower,node.right.upper)
			return self._sub(a,b)
			
		if node.name == 'mult':
			a = (node.left.lower,node.left.upper)
			b = (node.right.lower,node.right.upper)
			return self._mult(a,b)

		if node.name == 'div':
			a = (node.left.lower,node.left.upper)
			b = (node.right.lower,node.right.upper)
			return self._div(a,b) 
		
		if node.name == 'pow':
			a = (node.left.lower,node.left.upper)
			b = (node.right.lower,node.right.upper)
			return self._pow(a,b)

		if node.name == 'min':
			a = (node.left.lower,node.left.upper)
			b = (node.right.lower,node.right.upper)
			return self._min(a,b)

		if node.name == 'max':
			a = (node.left.lower,node.left.upper)
			b = (node.right.lower,node.right.upper)
			return self._max(a,b)

		if node.name == 'abs':
			# takes one node
			a = (node.left.lower,node.left.upper)
			return self._abs(a)
		
		if node.name == 'exp':
			# takes one node
			a = (node.left.lower,node.left.upper)
			return self._exp(a)

		else:
			raise NotImplementedError("Encountered an operation we do not yet support", node.name)
	
	def _add(self,a,b):
		"""
		Add two confidence intervals

		Parameters
		----------
		a : tuple
			Confidence interval like: (lower,upper)
		b : tuple
			Confidence interval like: (lower,upper)
		"""
		lower = self._protect_nan(
			a[0] + b[0],
			'lower')

		upper = self._protect_nan(
			a[1] + b[1],
			'upper')
		
		return (lower,upper)

	def _sub(self,a,b):
		"""
		Subract two confidence intervals

		Parameters
		----------
		a : tuple
			Confidence interval like: (lower,upper)
		b : tuple
			Confidence interval like: (lower,upper)
		"""
		lower = self._protect_nan(
				a[0] - b[1],
				'lower')
			
		upper = self._protect_nan(
			a[1] - b[0],
			'upper')

		return (lower,upper)

	def _mult(self,a,b):
		"""
		Multiply two confidence intervals

		Parameters
		----------
		a : tuple
			Confidence interval like: (lower,upper)
		b : tuple
			Confidence interval like: (lower,upper)
		"""        
		lower = self._protect_nan(
			min(a[0]*b[0],a[0]*b[1],a[1]*b[0],a[1]*b[1]),
			'lower')
		
		upper = self._protect_nan(
			max(a[0]*b[0],a[0]*b[1],a[1]*b[0],a[1]*b[1]),
			'upper')

		return (lower,upper)

	def _div(self,a,b):
		"""
		Divide two confidence intervals

		Parameters
		----------
		a : tuple
			Confidence interval like: (lower,upper)
		b : tuple
			Confidence interval like: (lower,upper)
		"""

		if b[0] < 0 < b[1]:
			# unbounded 
			lower = float('-inf')
			upper = float('inf')

		elif b[1] == 0:
			# reduces to multiplication of a*(-inf,1/b[0]]
			new_b = (float('-inf'),1/b[0])
			lower,upper = self._mult(a,new_b)

		elif b[0] == 0:
			# reduces to multiplication of a*(1/b[1],+inf)
			new_b = (1/b[1],float('inf'))
			lower,upper = self._mult(a,new_b)
		else:
			# b is either entirely negative or positive
			# reduces to multiplication of a*(1/b[1],1/b[0])
			new_b = (1/b[1],1/b[0])
			lower, upper = self._mult(a,new_b)

		return (lower,upper)

	def _pow(self,a,b):
		"""
		Get the confidence interval on 
		pow(A,B) where 
		A and B are both be intervals 

		Parameters
		----------
		a : tuple
			Confidence interval like: (lower,upper)
		b : tuple
			Confidence interval like: (lower,upper)
		"""

		# First, cases that are not allowed
		if a[0] < 0:
			raise ArithmeticError(
				f"Cannot compute interval: pow({a},{b}) because first argument contains negatives")
		if 0 in a and (b[0]<0 or b[1]<1):
			raise ZeroDivisionError("0.0 cannot be raised to a negative power")
		lower = self._protect_nan(
			min(
				pow(a[0],b[0]),
				pow(a[0],b[1]),
				pow(a[1],b[0]),
				pow(a[1],b[1])),
			'lower')
		
		upper = self._protect_nan(
			max(
				pow(a[0],b[0]),
				pow(a[0],b[1]),
				pow(a[1],b[0]),
				pow(a[1],b[1])),
			'upper')

		return (lower,upper)

	def _min(self,a,b):
		lower = min(a[0],b[0])
		upper = min(a[1],b[1])
		return (lower,upper)

	def _max(self,a,b):
		lower = max(a[0],b[0])
		upper = max(a[1],b[1])
		return (lower,upper)

	def _abs(self,a):
		"""
		Absolute value of a confidence interval

		Parameters
		----------
		a : tuple
			Confidence interval like: (lower,upper)
		"""
		abs_a0 = abs(a[0])
		abs_a1 = abs(a[1])
		
		lower = self._protect_nan(
			min(abs_a0,abs_a1) \
			if np.sign(a[0])==np.sign(a[1]) else 0,
			'lower')

		upper = self._protect_nan(
			max(abs_a0,abs_a1),
			'upper')

		return (lower,upper)

	def _exp(self,a):
		"""
		Exponentiate a confidence interval

		Parameters
		----------
		a : tuple
			Confidence interval like: (lower,upper)
		"""
		
		
		lower = self._protect_nan(
			np.exp(a[0]),
			'lower')

		upper = self._protect_nan(
			np.exp(a[1]),
			'upper')

		return (lower,upper)

	def reset_base_node_dict(self,reset_data=False):
		""" 
		Reset base node dict to initial state 
		This is all that should
		be necessary before each successive 
		propagation.

		"""
		for node_name in self.base_node_dict:
			self.base_node_dict[node_name]['computed'] = False
			self.base_node_dict[node_name]['lower'] = float('-inf')
			self.base_node_dict[node_name]['upper'] = float('inf')
			if reset_data:
				self.base_node_dict[node_name]['data_dict'] = None
				self.base_node_dict[node_name]['datasize'] = 0

		return
		
	def make_viz(self,title):
		""" 
		Make a graphviz diagram from a root node

		Parameters
		----------
		title : str
			The title you want to display at the top
			of the graph
		"""
		graph=graphviz.Digraph()
		graph.attr(label=title+'\n\n')
		graph.attr(labelloc='t')
		graph.node(str(self.root.index),self.root.__repr__(),
			shape='box',
			fontsize=f'{self.node_fontsize}')
		self.make_viz_helper(self.root,graph)
		return graph

	def make_viz_helper(self,root,graph):
		""" 
		Helper function for make_viz()
		Recurses through the parse tree
		and adds nodes and edges to the graph

		Parameters
		----------
		root : Node() class instance
			root of the parse tree
		graph: graphviz.Digraph() class instance
			The graphviz graph object
		"""
		if root.left:
			if root.left.node_type == 'base_node':
				style = 'filled'
				fillcolor='green'
			elif root.left.node_type == 'constant_node':
				style = 'filled'
				fillcolor='yellow'
			else:
				style = ''
				fillcolor='white'

			graph.node(str(root.left.index),str(root.left.__repr__()),
				style=style,fillcolor=fillcolor,shape='box',
				fontsize=f'{self.node_fontsize}')
			graph.edge(str(root.index),str(root.left.index))
			self.make_viz_helper(root.left,graph)

		if root.right:
			if root.right.node_type == 'base_node':
				style = 'filled'
				fillcolor='green'
			elif root.right.node_type == 'constant_node':
				style = 'filled'
				fillcolor='yellow'
			else:
				style = ''
				fillcolor='white'
			graph.node(str(root.right.index),str(root.right.__repr__()),
				style=style,fillcolor=fillcolor,shape='box',
				fontsize=f'{self.node_fontsize}')
			graph.edge(str(root.index),str(root.right.index))
			self.make_viz_helper(root.right,graph)   


