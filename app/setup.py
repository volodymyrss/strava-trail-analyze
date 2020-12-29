from setuptools import setup


setup(
        name='trailsapp',
        url="http://odahub.io",
        package_data     = {
            "": [
                "*.txt",
                "*.md",
                "*.rst",
                "*.py"
                ]
            },
        license='Creative Commons Attribution-Noncommercial-Share Alike license',
        long_description=open('README.md').read(),
        version="0.1.0"
        )
