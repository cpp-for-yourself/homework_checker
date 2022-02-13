# Homework checker #

This is a python module and script that can be used to check homeworks.

The idea behind the script is the following:
- There is a homework yaml file, see [`homework.yml`](homework_checker/core/tests/data/homework/example_job.yml) that follows the [schema](schema/schema.yml)
- In this file we define the structure of the homework
- The homework checker library knows how to execute certain types of tasks following the guides in the yaml file

It is expected that the submitted homework will follow the folder structure specified in the `homework.yml` file. 

## Core funcionality ##

### Run different tests ###
For now we support running tests for code written in different languages:
- c++
- bash

### Inject data into homeworks ###
We sometimes want to inject a certain folder before running tests, there is an option to do this here.

## How it works ##

I will probably not go into details here at this level of the package maturity. For now you can start digging from the [`check_homework.py`](homework_checker/check_homework.py) script and hopefully the code is clear enough. You can also look at the [`homework.yml`](homework_checker/core/tests/data/homework/example_job.yml) file that we use to test all the implemented functionality.
