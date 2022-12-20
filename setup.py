from setuptools import setup, find_packages

packages = ['q1pulse']
print('packages: {}'.format(packages))

setup(name="q1pulse",
	version="0.7.2",
    author="Sander de Snoo",
	packages = find_packages(),
    python_requires=">=3.7",
	install_requires=[
        'qblox_instruments',
      ],
	)
