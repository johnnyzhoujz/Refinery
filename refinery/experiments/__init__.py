"""
Customer experiment management system.

This module manages hypothesis versions and experiments for customers.
This is SEPARATE from Refinery's internal prompt versioning system.

- Refinery internal: refinery/prompts/ (Refinery's own prompts)
- Customer experiments: .refinery/prompt_versions/ (customer's hypothesis versions)
"""

from .customer_experiment_manager import CustomerExperimentManager

__all__ = ["CustomerExperimentManager"]
