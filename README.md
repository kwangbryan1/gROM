## Graph Reduced Order Models ##

In this repository we implement reduced order models for cardiovascular simulations using Graph Neural Networks (GNNs).

### Install the virtual environment ###

Let us first install `virtualenv`:

    pip install virtualenv

Then, from the root of the project:

    bash create_venv.sh

This will create a virtual environment `gromenv` following python packages: matplotlib, vtk, scipy, dgl, torch, sigopt.

### Download the data ###

The data can be downloaded [here](https://drive.google.com/open?id=1IByz6kyouNtNgnOxKrFK4DnAVu2yh6S1&authuser=lpego%40stanford.edu&usp=drive_fs).
Next, duplicate or rename `data_location_example.txt` as `data_location.txt` and set in it the location of the downloaded `gromdata` folder.

Note: `.vtp` files can be  inspected with [Paraview](https://www.paraview.org).

The `gROM_data` contains all the data necessary to train the GNN and you are welcome to skip the remaining parts of this section. However, it is possible to regenerate the data by launching `python graph1d/generate_graphs.py` from the root of the project.

### Train a GNN ###

From root, type

    python network1d/training.py

The parameters of the trained model and hyperparameters will be saved in `network/models`, in a folder named as the date and time when the training was launched.

### Test a GNN ###

Within the directory `graphs`, type

    python tester.py $NETWORKPATH

For example,

    python tester.py models/01.01.1990_00.00.00

This will save comparative plots in the same directory.
In the example, `models/01.01.1990_00.00.00` is a model generated after training (see Train a GNN).