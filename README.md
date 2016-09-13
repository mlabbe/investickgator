# InveSTICKgator #

Cross-platform joystick diagnostic tool.  Experience all joystick cross platform idiosyncrasies in a diagnostic tool instead of your own codebase.

[Downloadable binaries](https://github.com/mlabbe/investickgator/releases)

# Screenshots #

![Action Screenshot](screens/action.gif?raw=true)

## Changelog ##

release | what's new                          | date
--------|-------------------------------------|---------
1.0.0   | initial                             | 1/12/16
1.0.1   | about with buildinfo                | 9/12/16

## Building ##

If you just want to run Investickgator, check the releases tab in Github.  Precompiled versions are available to download.

`cd vendors`
`python3 compile_all_vendors.py -A x64`
`cd ../build`

InveSTICKgator uses [Premake5](https://premake.github.io/download.html) generated Makefiles and IDE project files.  The generated project files are checked in under `build/` so you don't have to download and use Premake in most cases.

### Linux ###

Before building, do this:

    apt-get install libgl1-mesa-dev x11proto-core-dev libx11-dev libglu1-mesa-dev


# Copyright and Credit #

Copyright &copy; 2016 Frogtoss Games, Inc. 

InveSTICKgator by Michael Labbe
[@frogtoss](https://www.twitter.com/frogtoss) 

## Support ##

[Contact author](http://www.frogtoss.com/contact.html)
