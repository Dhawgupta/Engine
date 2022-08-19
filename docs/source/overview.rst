Overview
========

This document provides an overview of how `Seldonian algorithms <https://seldonian.cs.umass.edu/Tutorials/>`_ (SAs) are implemented using this library. For a detailed description of what SAs are, see the `Seldonian Machine Learning Toolkit homepage  <https://seldonian.cs.umass.edu/>`_.

The most important piece of the Seldonian Engine API is the :py:class:`.SeldonianAlgorithm` class. One can run a Seldonian algorithm using a single API call on this class:

.. code::

	from seldonian.seldonian_algorithm import SeldonianAlgorithm
	from seldonian.utils.io_utils import load_pickle
	# here, the spec object is loaded from a file
	spec = load_pickle('spec.pkl')
	SA = SeldonianAlgorithm(spec)
	SA.run()

In this overview, we will go over what is in the :code:`spec` object and how to create it. We will also cover what :code:`SA.run()` actually does.

At the broadest scope, SAs consist of three parts: the interface, candidate selection, and the safety test. Below are the main components of the API that you will interact with within each of these parts.  

**Note**: The Engine supports supervised learning and reinforcement learning Seldonian algorithms. Where we could, we unified the code to work for both `regimes <https://seldonian.cs.umass.edu/Tutorials/glossary/#regime>`_. However, you may notice a pattern in the API where there is a regime-independent base class from which two child classes inherit, one for each of the two regimes.  

Interface
---------
The interface is a general concept for how the user provides inputs to the SA (for a full  conceptual description, see `the Seldonian Toolkit Overview <https://seldonian.cs.umass.edu/overview/#framework>`_). In the interface, the user provides (at minimum):

- the data
- the metadata
- the Behavioral constraints they want the SA to enforce.

The interface outputs a `Spec object`_, which consists of a complete specification used to run the seldonian algorithm.  

**Note**: The Engine library is not an interface. In general, it is up to a developer to design the interface for their specific application. We provide some example interfaces as part of the Seldonian Toolkit: a `command line interface <https://github.com/seldonian-toolkit/Engine/blob/main/interface/command_line_interface.py>`_ and a `graphical user interface <https://seldonian-toolkit.github.io/GUI>`_. 

Spec object
+++++++++++
The "spec" object (short for specification object) contains all of the inputs needed to run the Seldonian algorithm, the most important of which are:

- the dataset
- the underlying machine learning model
- the behavioral constraints 

Each of these is represented by an object in the Engine API. 

The :py:mod:`.spec` module contains the classes used to define spec objects. For the supervised learning regime, the :py:class:`.SupervisedSpec` class is used, and for the reinforcement learning regime the :py:class:`.RLSpec` class is used. We provide convenience functions to create these objects: :py:func:`.createSupervisedSpec` for supervised learning and :py:func:`.createRLspec` for reinforcement learning. 

Dataset object
++++++++++++++
The :py:mod:`.dataset` module contains the :py:class:`.SupervisedDataSet` (supervised learning) and the :py:class:`.RLDataSet` (reinforcement learning) classes. These objects contain the data points as well as metadata. These objects can be constructed manually, but we also provide a :py:class:`.DataSetLoader` class containing several convenience methods for loading data from files or arrays into the dataset objects. 

For example, one can create a :py:class:`.SupervisedDataSet` from a data file and metadata file using the :py:meth:`.load_supervised_dataset` method. The data file that you provide to this method via the :code:`filename` parameter must consist of rows of numbers that are comma-separated and have no header. Categorical columns must be numerically encoded. For example, the file format might look like:

.. code:: 

	0,1,622.6,491.56,439.93,707.64,663.65,557.09,711.37,731.31,509.8,1.33333
	1,0,538.0,490.58,406.59,529.05,532.28,447.23,527.58,379.14,488.64,2.98333
	1,0,455.18,440.0,570.86,417.54,453.53,425.87,475.63,476.11,407.15,1.97333
	0,1,756.91,679.62,531.28,583.63,534.42,521.4,592.41,783.76,588.26,2.53333
	...

where each row represents a different sample and each column is a feature or a label. This file should include *all* of the data you have, i.e., the data before partitioning into train, test, validation splits. The Engine will partition your data internally. The column names are intentionally excluded from this file and are provided in a separate metadata file, via the :code:`metadata_filename` parameter. 

The metadata file must be a JSON-formatted file containing several required ``key:value`` pairs depending on the regime of your problem. For supervised learning, the required keys are:

- "regime", which is set to 'supervised_learning' in this case
- "sub_regime", which is either 'classification' or 'regression'
- "columns", a list of all of the column names in your data file 
- "label_column", the column that you are trying to predict
- "sensitive_columns", a list of the column names for the `sensitive attributes <https://seldonian.cs.umass.edu/Tutorials/glossary/#sensitive_attributes>`_ in your dataset

For reinforcement learning, the required keys are:

- "regime", which is set to 'reinforcement_learning' in this case
- "columns", a list of the column names in your data file
- "RL_module_name", the name of the module within :py:mod:`.RL.environments` containing the RL environment class you want to use 
- "RL_class_name", the name of the class representing your environment inside the module you specified via the "RL_module_name" key 

Model object
++++++++++++
The biggest split between supervised and reinforcement learning in the Engine API is in how the underlying machine learning model is represented. Supervised learning models are represented as classes in the module: :py:mod:`.models.models`. The base class for classification (regression) is: :py:class:`.ClassificationModel` (:py:class:`.RegressionModel`). Any supervised learning model must inherit from either of these classes or one of their child classes. Some useful classes have already been created for running the tutorials, such as :py:class:`.LinearRegressionModel` and :py:class:`.LogisticRegressionModel`. These classes essentially wrap scikitlearn's model classes, for example, their `LinearRegression <https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LinearRegression.html>`_ model. 

Unless you are writing your own model, you will likely only need to know which of these models best fits your application. You may also want to choose from the primary objective functions, which are written as methods of the class. The primary objective function is one of the inputs to the spec object, though a default will be chosen if you do not explicitly pass one to the spec object. 

The reinforcement learning model is represented by the :py:class:`.RL_model` class. It is composed of an :py:class:`.Environment` class and an :py:class`.Agent` class, two things which supervised learning models do not have. All of these classes are found within modules of the larger :py:mod:`seldonian.RL` module. 

Behavioral constraints
++++++++++++++++++++++
In the `definition of a Seldonian algorithm <https://seldonian.cs.umass.edu/overview.html#algorithm>`_, `behavioral constraints <https://seldonian.cs.umass.edu/Tutorials/glossary/#behavioral_constraints>`_, :math:`(g_i,{\delta}_i)_{i=1}^n` are of a set of constraint functions, :math:`g_i`, and confidence levels, :math:`{\delta}_i`. Constraint functions need not be provided to the interface directly, but are often built by the engine from *constraint strings* provided by the user. 

Constraint strings
##################

Constraint strings contain the mathematical definition of the constraint functions, :math:`g_i`. These strings are written as Python strings and support five different types of sub-strings. 

1. The following math operators:

- :code:`+`, :code:`-`, :code:`*`, :code:`/`

2. These four native Python math functions: 

- :code:`min()`
- :code:`max()`
- :code:`abs()`
- :code:`exp()`

3. Constants. These can be integers or floats, such as "4" or "0.239".

4. Custom strings that trigger a call to a custom function. There are a set of special strings we call "measure functions" that correspond to statistical functions. For example, if :code:`Mean_Squared_Error` appears in a constraint string, the mean squared error will be calculated internally. Measure functions are specific to the machine learning regime. For a full list of currently supported measure functions, see: :py:mod:`.parse_tree.operators`. We left open the possibility that developers will want to define their own measure functions by adding to the current list. Measure functions are defined to estimate the confidence bounds on the mean value of a quantity. It is possible developers will want to bound something other than the mean, or do it in a way that differs from how we implemented bounds in the Engine. They would do this by creating their own custom base nodes. We wrote the `custom base node tutorial <https://seldonian.cs.umass.edu/Tutorials/tutorials/custom_base_node_tutorial>`_ to instruct new users how to create their own measure functions as well as custom base nodes.



5. The inequality strings "<=" or ">=". These are optional. Recall from `the definition of a Seldonian algorithm <https://seldonian.cs.umass.edu/overview.html#algorithm>`_ that we want :math:`g_i{\leq}0` to be satisfied. However, it can be cumbersome to write all of your constraint strings with a "<= 0" at the end. For convenience, we support constraint strings that both include and exclude the inequality symbols. For example, the four expressions will all be interpreted identically by the engine: 

- "Mean_Squared_Error <= 4.0"
- "Mean_Squared_Error - 4.0 <= 0"
- "Mean_Squared_Error - 4.0"
- "4.0 >= Mean_Squared_Error"

Constraint strings with more than one inequality string or with ">", "<", or "=" by themselves are not supported and will result in an error when the Engine tries to parse the constraint string.

Here are a few examples of basic constraint strings and their plain English interpretation:

- :code:`Mean_Squared_Error - 2.0`: "Ensure that the mean squared error is less than or equal to 2.0". Here, :code:`Mean_Squared_Error` is a special measure function for supervised regression problems. 

- :code:`0.88 <= TPR`: "Ensure that the True Positive Rate (TPR) is greater than or equal to 0.88". Here, :code:`TPR` is a measure function for supervised classification problems.

- :code:`J_pi_new >= 0.5`: "Ensure that the performance of the new policy (:code:`J_pi_new`) is greater than or equal to 0.5". Here, :code:`J_pi_new` is a measure function for reinforcement learning problems.

These basic constraint strings cover a number of use cases. However, they do not use information about the sensitive attributes (columns) in the dataset, which commonly appear in fairness definitions. The Engine supports a specification for filtering the data used to calculate the bound on the quantity defined by the measure function over one or more sensitive attributes. This is only supported for supervised learning datasets. The specification for doing this is as follows:

.. code::
	
	(measure_function | [ATR1,ATR2,...])

where :code:`measure_function` is a placeholder for the actual measure function in use and :code:`[ATR1,ATR2,...]` is a placeholder list of attributes (column names) from the dataset. The parentheses surrounding the statement are required in all cases.  

Let's say that an example dataset has four sensitive attributes: :code:`[M,F,R1,R2]`, standing for "male", "female", "race class 1", "race class 2").  The following constraint strings are examples of valid uses of measure functions subject to sensitive attributes. 

- :code:`abs((PR | [M]) - (PR | [F])) <= 0.15`: "Ensure that the absolute difference between the positive rate (the meaning of the measure function "PR") for males (M) and the positive rate for females (F) is less than or equal to 0.15". This constraint is called demographic parity (with a tolerance of 15%). Here, :code:`M` and :code:`F` must be columns of the dataset, and specified both in the :code:`columns` key and the :code:`sensitive_columns` key in the `Metadata file. We also see the use of a native Python function, :code:`abs()`, in this constraint string. 

- :code:`0.8 - min((PR | [M])/(PR | [F]),(PR | [F])/(PR | [M]))`: "Ensure that ratio of the positive rate for males (M) to the positive rate for females (F) or the inverse ratio is at least 0.8." This constraint is called disparate impact (with a tolerance of 0.8). We see the use of :code:`min()`, another native Python function in this constraint string. 

It is permitted to use more than one attribute for a given measure function. For example:

- :code:`(FPR | [F,R1]) <= 0.2`: "Ensure that the false positive rate (FPR) for females (F) belonging to race class 1 (R1) is less than or equal to 0.2. 

Note that the constraint strings only make up part of the behavioral constraints. The user must also specify the values of :math:`{\delta}` for each provided constraint string. The Engine bundles the list of behavioral constraints into :py:class:`.ParseTree` objects. The list of parse trees is one of the required inputs to the `Spec object`_.

.. _candidate_selection:

Candidate Selection
-------------------
:py:class:`.seldonian_algorithm.SeldonianAlgorithm` is a central class in the API that handles both candidate selection and the safety test. This class has a method :py:meth:`.seldonian_algorithm.SeldonianAlgorithm.run` that runs candidate selection and then the safety test using the outputs of candidate selection. The inputs to candidate selection are assembled from the spec object provided to the :py:class:`.seldonian_algorithm.SeldonianAlgorithm` object. 

There are currently two supported optimization techniques for candidate selection: 

1. Black box optimization with a barrier function. The barrier, which is shaped like the upper bound functions, is added to the cost function when any of the constraints are violated. This forces solutions toward the feasible set. 

2. Gradient descent on a `Lagrangian <https://en.wikipedia.org/wiki/Lagrange_multiplier#:~:text=In%20mathematical%20optimization%2C%20the%20method,chosen%20values%20of%20the%20variables).>`_:

.. math::

	{\mathcal{L(\mathbf{\theta,\lambda})}} = f(\mathbf{\theta}) + {\sum}_i^{n} {\lambda_i} g_i(\mathbf{\theta})

where :math:`\mathbf{\theta}` is the vector of model weights, :math:`f(\mathbf{\theta})` is the primary objective function, :math:`g_i(\mathbf{\theta})` is the ith constraint function of :math:`n` constraints, and :math:`\mathbf{\lambda}` is a vector of Lagrange multipliers, such that :math:`{\lambda_i}` is the Lagrange multiplier for the ith constraint. 

The `KKT <https://en.wikipedia.org/wiki/Karush%E2%80%93Kuhn%E2%80%93Tucker_conditions>`_ Theorem states that the saddle points of :math:`{\mathcal{L}}` are optima of the constrainted optimization problem:

	Optimize :math:`f({\theta})` subject to:
		
		:math:`g_i({\theta}){\leq}0, {\quad} i{\in}\{0{\ldots}n\}`


To find the saddle points we use gradient descent to obtain the global minimum over :math:`{\theta}` and simultaneous gradient *ascent* to obtain the global maximum over the multipliers, :math:`{\lambda}`.

In situations where the contraints are conflicting with the primary objective, vanilla gradient descent can result in oscillations of the solution near the feasible set boundary. These oscillations can be dampened using momentum in gradient descent. We implemented the adam optimizer as part of our gradient descent method, which includes momentum, and found that it mitigates the oscillations in all problems we have tested so far. 

Safety Test
-----------
The safety test is run on the candidate solution returned by candidate selection. Like candidate selection, the safety test is run inside of the :py:func:`.seldonian_algorithm.seldonian_algorithm` function. The inputs to the safety test are assembled from the spec object provided to the function. First, a :py:class:`.SafetyTest` object is created, then :py:meth:`.SafetyTest.run` is called to start the safety test.  

