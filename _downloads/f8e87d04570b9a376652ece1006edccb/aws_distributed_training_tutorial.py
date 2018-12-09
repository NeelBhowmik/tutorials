"""
PyTorch 1.0 Distributed Trainer with Amazon AWS
===============================================

**Author**: `Nathan Inkawhich <https://github.com/inkawhich>`_

**Edited by**: `Teng Li <https://github.com/teng-li>`_

"""


######################################################################
# In this tutorial we will show how to setup, code, and run a PyTorch 1.0
# distributed trainer across two multi-gpu Amazon AWS nodes. We will start
# with describing the AWS setup, then the PyTorch environment
# configuration, and finally the code for the distributed trainer.
# Hopefully you will find that there is actually very little code change
# required to extend your current training code to a distributed
# application, and most of the work is in the one-time environment setup.
#


######################################################################
# Amazon AWS Setup
# ----------------
#
# In this tutorial we will run distributed training across two multi-gpu
# nodes. In this section we will first cover how to create the nodes, then
# how to setup the security group so the nodes can communicate with
# eachother.
#
# Creating the Nodes
# ~~~~~~~~~~~~~~~~~~
#
# In Amazon AWS, there are seven steps to creating an instance. To get
# started, login and select **Launch Instance**.
#
# **Step 1: Choose an Amazon Machine Image (AMI)** - Here we will select
# the ``Deep Learning AMI (Ubuntu) Version 14.0``. As described, this
# instance comes with many of the most popular deep learning frameworks
# installed and is preconfigured with CUDA, cuDNN, and NCCL. It is a very
# good starting point for this tutorial.
#
# **Step 2: Choose an Instance Type** - Now, select the GPU compute unit
# called ``p2.8xlarge``. Notice, each of these instances has a different
# cost but this instance provides 8 NVIDIA Tesla K80 GPUs per node, and
# provides a good architecture for multi-gpu distributed training.
#
# **Step 3: Configure Instance Details** - The only setting to change here
# is increasing the *Number of instances* to 2. All other configurations
# may be left at default.
#
# **Step 4: Add Storage** - Notice, by default these nodes do not come
# with a lot of storage (only 75 GB). For this tutorial, since we are only
# using the STL-10 dataset, this is plenty of storage. But, if you want to
# train on a larger dataset such as ImageNet, you will have to add much
# more storage just to fit the dataset and any trained models you wish to
# save.
#
# **Step 5: Add Tags** - Nothing to be done here, just move on.
#
# **Step 6: Configure Security Group** - This is a critical step in the
# configuration process. By default two nodes in the same security group
# would not be able to communicate in the distributed training setting.
# Here, we want to create a **new** security group for the two nodes to be
# in. However, we cannot finish configuring in this step. For now, just
# remember your new security group name (e.g. launch-wizard-12) then move
# on to Step 7.
#
# **Step 7: Review Instance Launch** - Here, review the instance then
# launch it. By default, this will automatically start initializing the
# two instances. You can monitor the initialization progress from the
# dashboard.
#
# Configure Security Group
# ~~~~~~~~~~~~~~~~~~~~~~~~
#
# Recall that we were not able to properly configure the security group
# when creating the instances. Once you have launched the instance, select
# the *Network & Security > Security Groups* tab in the EC2 dashboard.
# This will bring up a list of security groups you have access to. Select
# the new security group you created in Step 6 (i.e. launch-wizard-12),
# which will bring up tabs called *Description, Inbound, Outbound, and
# Tags*. First, select the *Inbound* tab and *Edit* to add a rule to allow
# "All Traffic" from "Sources" in the launch-wizard-12 security group.
# Then select the *Outbound* tab and do the exact same thing. Now, we have
# effectively allowed all Inbound and Outbound traffic of all types
# between nodes in the launch-wizard-12 security group.
#
# Necessary Information
# ~~~~~~~~~~~~~~~~~~~~~
#
# Before continuing, we must find and remember the IP addresses of both
# nodes. In the EC2 dashboard find your running instances. For both
# instances, write down the *IPv4 Public IP* and the *Private IPs*. For
# the remainder of the document, we will refer to these as the
# **node0-publicIP**, **node0-privateIP**, **node1-publicIP**, and
# **node1-privateIP**. The public IPs are the addresses we will use to SSH
# in, and the private IPs will be used for inter-node communication.
#


######################################################################
# Environment Setup
# -----------------
#
# The next critical step is the setup of each node. Unfortunately, we
# cannot configure both nodes at the same time, so this process must be
# done on each node separately. However, this is a one time setup, so once
# you have the nodes configured properly you will not have to reconfigure
# for future distributed training projects.
#
# The first step, once logged onto the node, is to create a new conda
# environment with python 3.6 and numpy. Once created activate the
# environment.
#
# ::
#
#     $ conda create -n nightly_pt python=3.6 numpy
#     $ source activate nightly_pt
#
# Next, we will install a nightly build of Cuda 9.0 enabled PyTorch with
# pip in the conda environment.
#
# ::
#
#     $ pip install torch_nightly -f https://download.pytorch.org/whl/nightly/cu90/torch_nightly.html
#
# We must also install torchvision so we can use the torchvision model and
# dataset. At this time, we must build torchvision from source as the pip
# installation will by default install an old version of PyTorch on top of
# the nightly build we just installed.
#
# ::
#
#     $ cd
#     $ git clone https://github.com/pytorch/vision.git
#     $ cd vision
#     $ python setup.py install
#
# And finally, **VERY IMPORTANT** step is to set the network interface
# name for the NCCL socket. This is set with the environment variable
# ``NCCL_SOCKET_IFNAME``. To get the correct name, run the ``ifconfig``
# command on the node and look at the interface name that corresponds to
# the node's *privateIP* (e.g. ens3). Then set the environment variable as
#
# ::
#
#     $ export NCCL_SOCKET_IFNAME=ens3
#
# Remember, do this on both nodes. You may also consider adding the
# NCCL\_SOCKET\_IFNAME setting to your *.bashrc*. An important observation
# is that we did not setup a shared filesystem between the nodes.
# Therefore, each node will have to have a copy of the code and a copy of
# the datasets. For more information about setting up a shared network
# filesystem between nodes, see
# `here <https://aws.amazon.com/blogs/aws/amazon-elastic-file-system-shared-file-storage-for-amazon-ec2/>`__.
#


######################################################################
# Distributed Training Code
# -------------------------
#
# With the instances running and the environments setup we can now get
# into the training code. Most of the code here has been taken from the
# `PyTorch ImageNet
# Example <https://github.com/pytorch/examples/tree/master/imagenet>`__
# which also supports distributed training. This code provides a good
# starting point for a custom trainer as it has much of the boilerplate
# training loop, validation loop, and accuracy tracking functionality.
# However, you will notice that the argument parsing and other
# non-essential functions have been stripped out for simplicity.
#
# In this example we will use
# `torchvision.models.resnet18 <https://pytorch.org/docs/stable/torchvision/models.html#torchvision.models.resnet18>`__
# model and will train it on the
# `torchvision.datasets.STL10 <https://pytorch.org/docs/stable/torchvision/datasets.html#torchvision.datasets.STL10>`__
# dataset. To accomodate for the dimensionality mismatch of STL-10 with
# Resnet18, we will resize each image to 224x224 with a transform. Notice,
# the choice of model and dataset are orthogonal to the distributed
# training code, you may use any dataset and model you wish and the
# process is the same. Lets get started by first handling the imports and
# talking about some helper functions. Then we will define the train and
# test functions, which have been largely taken from the ImageNet Example.
# At the end, we will build the main part of the code which handles the
# distributed training setup. And finally, we will discuss how to actually
# run the code.
#


######################################################################
# Imports
# ~~~~~~~
#
# The important distributed training specific imports here are
# `torch.nn.parallel <https://pytorch.org/docs/stable/nn.html#torch.nn.parallel.DistributedDataParallel>`__,
# `torch.distributed <https://pytorch.org/docs/stable/distributed.html>`__,
# `torch.utils.data.distributed <https://pytorch.org/docs/stable/data.html#torch.utils.data.distributed.DistributedSampler>`__,
# and
# `torch.multiprocessing <https://pytorch.org/docs/stable/multiprocessing.html>`__.
# It is also important to set the multiprocessing start method to *spawn*
# or *forkserver* (only supported in Python 3),
# as the default is *fork* which may cause deadlocks when using multiple
# worker processes for dataloading.
#





















######################################################################
# Helper Functions
# ~~~~~~~~~~~~~~~~
#
# We must also define some helper functions and classes that will make
# training easier. The ``AverageMeter`` class tracks training statistics
# like accuracy and iteration count. The ``accuracy`` function computes
# and returns the top-k accuracy of the model so we can track learning
# progress. Both are provided for training convenience but neither are
# distributed training specific.
#



































######################################################################
# Train Functions
# ~~~~~~~~~~~~~~~
#
# To simplify the main loop, it is best to separate a training epoch step
# into a function called ``train``. This function trains the input model
# for one epoch of the *train\_loader*. The only distributed training
# artifact in this function is setting the
# `non\_blocking <https://pytorch.org/docs/stable/notes/cuda.html#use-pinned-memory-buffers>`__
# attributes of the data and label tensors to ``True`` before the forward
# pass. This allows asynchronous GPU copies of the data meaning transfers
# can be overlapped with computation. This function also outputs training
# statistics along the way so we can track progress throughout the epoch.
#
# The other function to define here is ``adjust_learning_rate``, which
# decays the initial learning rate at a fixed schedule. This is another
# boilerplate trainer function that is useful to train accurate models.
#





























































######################################################################
# Validation Function
# ~~~~~~~~~~~~~~~~~~~
#
# To track generalization performance and simplify the main loop further
# we can also extract the validation step into a function called
# ``validate``. This function runs a full validation step of the input
# model on the input validation dataloader and returns the top-1 accuracy
# of the model on the validation set. Again, you will notice the only
# distributed training feature here is setting ``non_blocking=True`` for
# the training data and labels before they are passed to the model.
#















































######################################################################
# Inputs
# ~~~~~~
#
# With the helper functions out of the way, now we have reached the
# interesting part. Here is where we will define the inputs for the run.
# Some of the inputs are standard model training inputs such as batch size
# and number of training epochs, and some are specific to our distributed
# training task. The required inputs are:
#
# -  **batch\_size** - batch size for *each* process in the distributed
#    training group. Total batch size across distributed model is
#    batch\_size\*world\_size
#
# -  **workers** - number of worker processes used with the dataloaders in
#    each process
#
# -  **num\_epochs** - total number of epochs to train for
#
# -  **starting\_lr** - starting learning rate for training
#
# -  **world\_size** - number of processes in the distributed training
#    environment
#
# -  **dist\_backend** - backend to use for distributed training
#    communication (i.e. NCCL, Gloo, MPI, etc.). In this tutorial, since
#    we are using several multi-gpu nodes, NCCL is suggested.
#
# -  **dist\_url** - URL to specify the initialization method of the
#    process group. This may contain the IP address and port of the rank0
#    process or be a non-existant file on a shared file system. Here,
#    since we do not have a shared file system this will incorporate the
#    **node0-privateIP** and the port on node0 to use.
#



# Batch Size for training and testing


# Number of additional worker processes for dataloading


# Number of epochs to train for


# Starting Learning Rate


# Number of distributed processes


# Distributed backend type


# Url used to setup distributed training



######################################################################
# Initialize process group
# ~~~~~~~~~~~~~~~~~~~~~~~~
#
# One of the most important parts of distributed training in PyTorch is to
# properly setup the process group, which is the **first** step in
# initializing the ``torch.distributed`` package. To do this, we will use
# the ``torch.distributed.init_process_group`` function which takes
# several inputs. First, a *backend* input which specifies the backend to
# use (i.e. NCCL, Gloo, MPI, etc.). An *init\_method* input which is
# either a url containing the address and port of the rank0 machine or a
# path to a non-existant file on the shared file system. Note, to use the
# file init\_method, all machines must have access to the file, similarly
# for the url method, all machines must be able to communicate on the
# network so make sure to configure any firewalls and network settings to
# accomodate. The *init\_process\_group* function also takes *rank* and
# *world\_size* arguments which specify the rank of this process when run
# and the number of processes in the collective, respectively.
# The *init\_method* input can also be "env://". In this case, the address
# and port of the rank0 machine will be read from the following two
# environment variables respectively: MASTER_ADDR, MASTER_PORT.  If *rank*
# and *world\_size* arguments are not specified in the *init\_process\_group*
# function, they both can be read from the following two environment
# variables respectively as well: RANK, WORLD_SIZE.
#
# Another important step, especially when each node has multiple gpus is
# to set the *local\_rank* of this process. For example, if you have two
# nodes, each with 8 GPUs and you wish to train with all of them then
# :math:`world\_size=16` and each node will have a process with local rank
# 0-7. This local\_rank is used to set the device (i.e. which GPU to use)
# for the process and later used to set the device when creating a
# distributed data parallel model. It is also recommended to use NCCL
# backend in this hypothetical environment as NCCL is preferred for
# multi-gpu nodes.
#


# Initialize Process Group
# v1 - init with url

# v2 - init with file
# dist.init_process_group(backend="nccl", init_method="file:///home/ubuntu/pt-distributed-tutorial/trainfile", rank=int(sys.argv[1]), world_size=world_size)
# v3 - init with environment variables
# dist.init_process_group(backend="nccl", init_method="env://", rank=int(sys.argv[1]), world_size=world_size)


# Establish Local Rank and set device on this node





######################################################################
# Initialize Model
# ~~~~~~~~~~~~~~~~
#
# The next major step is to initialize the model to be trained. Here, we
# will use a resnet18 model from ``torchvision.models`` but any model may
# be used. First, we initialize the model and place it in GPU memory.
# Next, we make the model ``DistributedDataParallel``, which handles the
# distribution of the data to and from the model and is critical for
# distributed training. The ``DistributedDataParallel`` module also
# handles the averaging of gradients across the world, so we do not have
# to explicitly average the gradients in the training step.
#
# It is important to note that this is a blocking function, meaning
# program execution will wait at this function until *world\_size*
# processes have joined the process group. Also, notice we pass our device
# ids list as a parameter which contains the local rank (i.e. GPU) we are
# using. Finally, we specify the loss function and optimizer to train the
# model with.
#


# Construct Model

# Make model DistributedDataParallel


# define loss function (criterion) and optimizer




######################################################################
# Initialize Dataloaders
# ~~~~~~~~~~~~~~~~~~~~~~
#
# The last step in preparation for the training is to specify which
# dataset to use. Here we use the `STL-10
# dataset <https://cs.stanford.edu/~acoates/stl10/>`__ from
# `torchvision.datasets.STL10 <https://pytorch.org/docs/stable/torchvision/datasets.html#torchvision.datasets.STL10>`__.
# The STL10 dataset is a 10 class dataset of 96x96px color images. For use
# with our model, we resize the images to 224x224px in the transform. One
# distributed training specific item in this section is the use of the
# ``DistributedSampler`` for the training set, which is designed to be
# used in conjunction with ``DistributedDataParallel`` models. This object
# handles the partitioning of the dataset across the distributed
# environment so that not all models are training on the same subset of
# data, which would be counterproductive. Finally, we create the
# ``DataLoader``'s which are responsible for feeding the data to the
# processes.
#
# The STL-10 dataset will automatically download on the nodes if they are
# not present. If you wish to use your own dataset you should download the
# data, write your own dataset handler, and construct a dataloader for
# your dataset here.
#


# Define the transform for the data. Notice, we must resize to 224x224 with this dataset and model.





# Initialize Datasets. STL10 will automatically download if not present



# Create DistributedSampler to handle distributing the dataset across nodes when training
# This can only be called after torch.distributed.init_process_group is called


# Create the Dataloaders to feed data to the training and validation steps




######################################################################
# Training Loop
# ~~~~~~~~~~~~~
#
# The last step is to define the training loop. We have already done most
# of the work for setting up the distributed training so this is not
# distributed training specific. The only detail is setting the current
# epoch count in the ``DistributedSampler``, as the sampler shuffles the
# data going to each process deterministically based on epoch. After
# updating the sampler, the loop runs a full training epoch, runs a full
# validation step then prints the performance of the current model against
# the best performing model so far. After training for num\_epochs, the
# loop exits and the tutorial is complete. Notice, since this is an
# exercise we are not saving models but one may wish to keep track of the
# best performing model then save it at the end of training (see
# `here <https://github.com/pytorch/examples/blob/master/imagenet/main.py#L184>`__).
#



























######################################################################
# Running the Code
# ----------------
#
# Unlike most of the other PyTorch tutorials, this code may not be run
# directly out of this notebook. To run, download the .py version of this
# file (or convert it using
# `this <https://gist.github.com/chsasank/7218ca16f8d022e02a9c0deb94a310fe>`__)
# and upload a copy to both nodes. The astute reader would have noticed
# that we hardcoded the **node0-privateIP** and :math:`world\_size=4` but
# input the *rank* and *local\_rank* inputs as arg[1] and arg[2] command
# line arguments, respectively. Once uploaded, open two ssh terminals into
# each node.
#
# -  On the first terminal for node0, run ``$ python main.py 0 0``
#
# -  On the second terminal for node0 run ``$ python main.py 1 1``
#
# -  On the first terminal for node1, run ``$ python main.py 2 0``
#
# -  On the second terminal for node1 run ``$ python main.py 3 1``
#
# The programs will start and wait after printing "Initialize Model..."
# for all four processes to join the process group. Notice the first
# argument is not repeated as this is the unique global rank of the
# process. The second argument is repeated as that is the local rank of
# the process running on the node. If you run ``nvidia-smi`` on each node,
# you will see two processes on each node, one running on GPU0 and one on
# GPU1.
#
# We have now completed the distributed training example! Hopefully you
# can see how you would use this tutorial to help train your own models on
# your own datasets, even if you are not using the exact same distributed
# envrionment. If you are using AWS, don't forget to **SHUT DOWN YOUR
# NODES** if you are not using them or you may find an uncomfortably large
# bill at the end of the month.
#
# **Where to go next**
#
# -  Check out the `launcher
#    utility <https://pytorch.org/docs/stable/distributed.html#launch-utility>`__
#    for a different way of kicking off the run
#
# -  Check out the `torch.multiprocessing.spawn
#    utility <https://pytorch.org/docs/master/multiprocessing.html#spawning-subprocesses>`__
#    for another easy way of kicking off multiple distributed processes.
#    `PyTorch ImageNet Example <https://github.com/pytorch/examples/tree/master/imagenet>`__
#    has it implemented and can demonstrate how to use it.
#
# -  If possible, setup a NFS so you only need one copy of the dataset
#


# %%%%%%RUNNABLE_CODE_REMOVED%%%%%%