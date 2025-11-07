import pandas as pd

df = pd.read_csv("data.csv")
print(df.describe())

for column in df.columns:
    print(f"\n--- Analyzing Column: {column} ---")

    # Check data type
    if pd.api.types.is_numeric_dtype(df[column]):
        # Numeric column analysis
        print("Data Type: Numeric")
        print(df[column].describe())  # Basic descriptive statistics

        # Outlier detection using IQR (Interquartile Range)
        Q1 = df[column].quantile(0.25)
        Q3 = df[column].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR

        outliers = df[(df[column] < lower_bound) | (df[column] > upper_bound)][column]
        if not outliers.empty:
            print(f"Potential Outliers (IQR Method):\n{outliers}")
        else:
            print("No obvious outliers detected by IQR method.")

    elif pd.api.types.is_string_dtype(df[column]) or pd.api.types.is_categorical_dtype(
        df[column]
    ):
        # Categorical/Text column analysis
        print("Data Type: Categorical/Text")
        print(df[column].value_counts())  # Frequency distribution of unique values

    else:
        print("Data Type: Other (e.g., Datetime, Boolean)")
        print(df[column].head())  # Display first few values for inspection
