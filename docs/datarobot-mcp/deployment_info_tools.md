# Deployment information tools for building prediction datasets

These tools help AI agents understand what input data a deployment expects and create valid prediction datasets at runtime. They are especially useful when an agent must generate prediction data without human help.

## Tools overview

### `deployment_get_info`

Use this tool to inspect the features required by a deployment.

It returns:

- feature names and types, such as numeric, categorical, text, and date
- feature importance scores
- target information
- time series settings, when applicable

Typical use case: an agent needs to determine which columns and data types are required before generating input data.

Example response:

```json
{
  "deployment_id": "abc123",
  "model_type": "Regression",
  "target": "sales",
  "target_type": "Regression",
  "features": [
    {
      "feature_name": "temperature",
      "feature_type": "numeric",
      "importance": 0.85,
      "is_target": false
    },
    {
      "feature_name": "promotion",
      "feature_type": "categorical",
      "importance": 0.65,
      "is_target": false
    }
  ],
  "time_series_config": {
    "datetime_column": "date",
    "forecast_window_start": 1,
    "forecast_window_end": 7,
    "series_id_columns": ["store_id"]
  }
}
```

### `deployment_generate_prediction_sample`

Use this tool to retrieve sample training data for the deployment.

It returns:

- example rows from the training data
- metadata about the full dataset

Typical use case: an agent needs real examples of valid input values, formats, or patterns.

### `generate_prediction_data_template`

Use this tool to create a prediction template with the correct structure.

It returns:

- all required columns in the expected order
- sample values based on feature types
- metadata comments that explain the model

Typical use case: an agent needs a valid starting point that it can fill in with user-specific values.

### `deployment_validate_prediction_data`

Use this tool to confirm that a dataset can be used for prediction.

It returns:

- errors, such as missing required features or invalid types
- warnings, such as missing low-importance features
- informational messages, such as extra columns that will be ignored

Typical use case: an agent validates generated data before submitting it for prediction.

## Example agent workflow

Suppose a user says:

`I want to predict sales for next week for store_A with temperatures of 75F each day and no promotions.`

An agent could respond by following this workflow:

1. Retrieve the deployment requirements:

   ```text
   get_deployment_features(deployment_id="sales_forecast_deployment")
   ```

   The agent learns that it needs `date`, `temperature`, `promotion`, and `store_id`.

2. Generate a template:

   ```text
   generate_prediction_data_template(
       deployment_id="sales_forecast_deployment",
       n_rows=7
   )
   ```

   The agent receives a seven-row CSV template.

3. Fill in the user-specific values:

   - set `temperature` to `75` for all rows
   - set `promotion` to `0` for all rows
   - set `store_id` to `"store_A"` for all rows
   - set the dates for the next seven days

4. Validate the completed data:

   ```text
   validate_prediction_data(
       deployment_id="sales_forecast_deployment",
       file_path="prediction_data.csv"
   )
   ```

   The agent confirms that the data is valid.

5. Submit the prediction request:

   ```text
   predict_realtime(
       deployment_id="sales_forecast_deployment",
       file_path="prediction_data.csv",
       forecast_point="2024-06-01"
   )
   ```

## Why these tools matter for agents

These tools make the prediction workflow easier for agents because they provide:

- self-documenting metadata about required inputs
- type information that helps prevent formatting errors
- validation before prediction requests are sent
- sample data that shows realistic input values
- templates that reduce the amount of data assembly an agent must do

## Why these tools work well with LLMs

The outputs are designed to be easy for LLMs to interpret and reuse:

- JSON for structured metadata
- CSV for tabular data
- validation messages for troubleshooting
- template comments for additional context

Together, these tools enable agents to build and validate prediction datasets with less manual intervention.