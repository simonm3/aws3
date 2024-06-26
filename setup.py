"""
This file is automatically generated by the autogen package.
Please edit the marked area only. Other areas will be
overwritten when autogen is rerun.
"""

from setuptools import setup

params = dict(
    name="aws3",
    description="aws3",
    version="0.0.0",
    url="",
    install_requires=["boto3", "click"],
    packages=["aws3"],
    package_data={},
    include_package_data=True,
    py_modules=[],
    scripts=None,
)

########## EDIT BELOW THIS LINE ONLY ##########

params["entry_points"] = {
    "console_scripts": [
        "aws3 = aws3.aws3:c",
    ],
}

########## EDIT ABOVE THIS LINE ONLY ##########

setup(**params)
