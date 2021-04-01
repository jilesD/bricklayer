import setuptools

with open('dbricks_utils/__version__.py') as fd:
    version = fd.read().split('=')[1].strip().strip("'")

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="dbricks_utils",
    version=version,
    author="Intelematics",
    description="Databricks utils",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/intelematics/dac-dbs-utils",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=[
          'databricks_cli',
      ]
)
