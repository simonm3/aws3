Overview
========

Main purpose is to have a simple cli to start/stop aws spot instances. It can also be used for any aws resources.

Uses aws stacks which are a relatively new construct. The benefits of a stack are:

* stack definition is declarative using yaml rather than code. This avoids the temptation to tweak code frequently
* stack file can be reused or copied/edited for other projects
* stack defines what is needed e.g. memory/processing power rather than a specific instance type. This is useful when specific instance types are not available
* stack can include multiple aws resources. All resources are created/deleted together so avoiding any accidental remnants.

The templates folder includes example stack files for launching an instance and spot instance.

Note since 2020 it has been possible to stop/restart spot instances. Have not used this as it has various constraints such as not working with a spot fleet. Also generally I want to keep snapshots at each stop.

TODO: more testing. appears to works with the example templates but requires wider range of usage.

Usage
=====

Usage: aws3 [OPTIONS] COMMAND [ARGS]...

  cli to start/stop instances

Options:
  --help  Show this message and exit.

Commands:
  * start      start a stack from a template args=template [name]
  * stop       create image and stop stack args=name
  * terminate  terminate stack and delete image args=name
  * show       show aws resources currently used


Dependencies
============

boto3 - aws api
click - for building command line interfaces using decorators

Files
=====

aws3 - main cli
utils - simplifications of the aws/boto3 api
names.csv - list of names to assign to stacks/resources
templates folder - starter templates for stacks