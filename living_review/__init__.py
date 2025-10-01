"""
living_review
=============

A Python package for managing and analyzing **Living Reviews**,
with a focus on applications in particle accelerators and
machine learning.

This package provides:
- Data model (`Paper` class) to represent scientific papers.
- Fetchers for multiple bibliographic APIs (arXiv, InspireHEP, HAL,
  OpenAlex, Crossref).
- Semantic filtering and classification of papers using
  sentence-transformers.
- Statistics computation for bibliometrics and trends.
- Export utilities to JSON and HTML.
- Logging of scans and errors.
- A pipeline (`LivingReviewPipeline`) to orchestrate the entire workflow.
- A CLI (`living_review.cli`) for running scans from the terminal.

Attributes
----------
__version__ : str
    Current version of the package.
"""

__version__ = "0.1.0"
__author__ = "Adnan GHRIBI <adnan.ghribi@ganil.fr> <adnan.ghribi@cern.ch> <adnan.ghribi@cnrs.fr>"
__license__ = "MIT"
__copyright__ = "2024, Adnan GHRIBI"
__all__ = ["__version__", "__author__", "__license__", "__copyright__"]
__docformat__ = "restructuredtext"
__package_name__ = "ML_ACC_living_review"
__url__ = "https://github.com/yourusername/living_review"