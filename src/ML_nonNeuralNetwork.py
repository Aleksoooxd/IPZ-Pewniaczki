import os
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.metrics import classification_report, confusion_matrix
from imblearn.over_sampling import SMOTE

# Mapy do zamiany wartości tekstowych na numeryczne
consensus_map = {
    "H": 1,
    "D": 0,
    "A": 2,
    "No Consensus": -1
}
FTR_map = {
    "H": 1,
    "D": 0,
    "A": 2
}

# Ścieżki do danych wejściowych i wynikowych
output_path = os.path.join('..', 'ML_output_data')
input_path = os.path.join('..', 'Data', 'FinalData', 'AllBookmakers')

# Tworzenie folderu wynikowego, jeśli nie istnieje
os.makedirs(output_path, exist_ok=True)

for filename in os.listdir(input_path):
    if filename.endswith(".csv"):
        try:
            print(f"Processing {filename}")

            # Wczytywanie danych
            filePath = os.path.join(input_path, filename)
            data = pd.read_csv(filePath)

            # Mapowanie kolumn Consensus i FTR
            data['Consensus'] = data['Consensus'].map(consensus_map)
            data['FTR'] = data['FTR'].map(FTR_map)



            # Wybór cech i celu (przykład: isSuprise jako cel)
            target_column = 'isSuprise'
            numeric_data = data.select_dtypes(include=['number'])

            X = numeric_data.drop(columns=[target_column])
            y = numeric_data[target_column]

            # Podział danych na treningowe i testowe (90:10)
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.1, random_state=42, stratify=y
            )

            # Standaryzacja danych
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            # Równoważenie danych przy użyciu SMOTE
            smote = SMOTE(random_state=42)
            X_train_balanced, y_train_balanced = smote.fit_resample(X_train_scaled, y_train)

            # Lista klasyfikatorów
            classifiers = {
                "Random Forest": RandomForestClassifier(random_state=42),
                "Logistic Regression": LogisticRegression(random_state=42, max_iter=500),
                "Support Vector Machine": SVC(random_state=42, probability=True),
                "K-Nearest Neighbors": KNeighborsClassifier(),
                "Naive Bayes": GaussianNB(),
                "Gradient Boosting": GradientBoostingClassifier(random_state=42)
            }

            # Iteracja po klasyfikatorach
            for clf_name, clf in classifiers.items():
                print(f"\n{clf_name} Results:")
                clf.fit(X_train_balanced, y_train_balanced)
                predictions = clf.predict(X_test_scaled)

                # Macierz konfuzji i raport
                confusion = confusion_matrix(y_test, predictions)
                report = classification_report(y_test, predictions)

                print("\t\tMacierz konfuzji:")
                print(confusion)
                print("====================")
                print("\t\tMiary:")
                print(report)

            print(f"End of processing {filename}")
        except Exception as e:
            print(f"Error processing {filename}: {e}")
