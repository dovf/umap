Fuzzing with Umap and Kitty
===========================

You can perform advanced USB host fuzzing using the Umap-Kitty integration.

Since kitty is not python3 compatible,
we need to run kitty and umap in two separate environments.
I use pyenv with two separate shells.


Setup (only once)
-----------------

Install python versions
+++++++++++++++++++++++

This will take a while ...

    $ pyenv install 3.4.4
    $ pyenv install 2.7.9

Install kitty on python3 environment
++++++++++++++++++++++++++++++++++++

    $ pyenv shell 3.4.4
    $ pip install git+https://github.com/cisco-sas/kitty.git#egg=kitty

Install kitty and katnip on python2 environment
+++++++++++++++++++++++++++++++++++++++++++++++

    $ pyenv shell 2.7.9
    $ pip install git+https://github.com/cisco-sas/kitty.git#egg=kitty
    $ pip install git+https://github.com/cisco-sas/katnip.git#egg=katnip

Usage
-----

You can run different scenarios with umap/kitty.
The basic tests are for the enumeration steps,
at this point, you will not need a specific device,
so let's start by using the umap stack as a keyboard:

Step #1 - Connect facedancer
++++++++++++++++++++++++++++

Connect the facedancer to the computer and the target.
We will assume for now that the facedancer appears on your machine as
**/dev/ttyUSB0** device.

Step #2 - Run the fuzzer
++++++++++++++++++++++++

The fuzzer should start first, and wait for the umap stack.

    $ pyenv shell 2.7.9
    $ cd <umap-dir>
    $ ./fuzzer.py

Step #3 - Start the stack
+++++++++++++++++++++++++

In a sperate shell, let's start the umap stack.
We specify the device of the facedancer (**/dev/ttyUSB0**).
We also tell umap to emulate a keyboard.

    $ pyenv shell 3.4.4
    $ cd <umap-dir>
    $ ./umap_stack.py fuzz --port /dev/ttyUSB0  --device keyboard

Step #4 - Monitor fuzzing progress
++++++++++++++++++++++++++++++++++

At this point, the fuzzer is running.
You can now monitor the progress of the fuzzing session
either via browser (http://localhost:26000/)
or via command line (``kitty-web-client info``)