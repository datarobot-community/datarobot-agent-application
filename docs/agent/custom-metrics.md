# Custom metrics

This template covers custom metrics in a DataRobot deployment: create a custom metric on a deployment, then push values with explicit timestamps or as a single "now" sample.

## Prerequisites

Install the [DataRobot Python API Client](https://pypi.org/project/datarobot/) and configure a DataRobot API endpoint and API token.

## Steps to work with custom metrics

Complete the following steps to create, retrieve, and submit values for a custom metric.

### 1. Create and retrieve a custom metric

Use `CustomMetric.create()` with the deployment ID, metric name, units, whether the metric is per-model or deployment-wide, how values aggregate, and whether higher or lower values are better.

```python
from datarobot.models.deployment import CustomMetric
from datarobot.enums import CustomMetricAggregationType, CustomMetricDirectionality

custom_metric = CustomMetric.create(
    deployment_id="<deployment_id>",
    name="My real-time metric",
    units="score",
    is_model_specific=True,
    aggregation_type=CustomMetricAggregationType.AVERAGE,
    directionality=CustomMetricDirectionality.HIGHER_IS_BETTER,
)
```

Once a metric is created, retrieve it with:

```python
from datarobot.models.deployment import CustomMetric

custom_metric = CustomMetric.get(deployment_id="<deployment_id>", custom_metric_id="<custom_metric_id>")
```

List all metrics for a deployment using:

```python
from datarobot.models.deployment import CustomMetric

custom_metrics = CustomMetric.list(deployment_id="<deployment_id>")
```

### 2. Submit a value

Once a custom metric is created, submit values to it multiple times. A new metric is not required for each tracked value.

For deployment-specific metrics:

```python
custom_metric.submit_single_value(value=16)
```

For model-specific metrics:

```python
custom_metric.submit_single_value(value=16, model_package_id="<model_package_id>")
```

The model package ID can be retrieved from a deployment object and used for submitting values to the current model:

```python
from datarobot.models.deployment import Deployment

model_package_id = Deployment.get("deployment_id").model_package['id']
```

## Quick reference

For more information about using custom metrics, see the custom metric page in the [DataRobot Python API client documentation](https://docs.datarobot.com/en/docs/api/dev-learning/python/mlops/custom_metrics.html).
