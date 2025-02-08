import os
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from imblearn.over_sampling import SMOTE
from sklearn.tree import DecisionTreeClassifier
from xgboost import XGBClassifier
import datetime
from openpyxl.workbook import Workbook
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
input_path = os.path.join('..', 'Data', 'FinalData', 'AllBookmakers')

# nowDate = datetime.datetime.now()
# output_path = os.path.join('..', 'MachineLearning_Result')
# if not os.path.exists(output_path):
#     os.makedirs(output_path)
# writer = pd.ExcelWriter(os.path.join(output_path, f'ML_result_{nowDate.month}_{nowDate.year}.xlsx'), engine='openpyxl')


fileInDir = os.listdir(input_path)

try:
    for file in fileInDir:
        if file.endswith(".csv"):
            print(f'========= Machine Lerning for file {file} =========')
            data = pd.read_csv(os.path.join(input_path, file))
            pd.set_option('display.max_columns', None)
            pd.set_option('display.max_rows', None)

            data['Date'] = pd.to_datetime(data['Date'], format='%d/%m/%Y')
            data['Consensus'] = data['Consensus'].map(consensus_map)
            data['FTR'] = data['FTR'].map(FTR_map)
            ## brak pomyslu na konwersje data['Season'] z object na cosik???

            OneHotEncoed_Data = pd.get_dummies(data, columns=['HomeTeam', 'AwayTeam'])
            # print(OneHotEncoed_Data.dtypes)

            X = OneHotEncoed_Data.drop(
                columns=['Date', 'FTR', 'isSuprise', 'Season', 'isSuprise_H', 'isSuprise_D', 'isSuprise_A', 'Div'])
            y = OneHotEncoed_Data['isSuprise']

            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.1, random_state=42)

            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            smote = SMOTE(random_state=42)
            X_train_smote, y_train_smote = smote.fit_resample(X_train_scaled, y_train)

            classifiers = {
                "Random Forest": RandomForestClassifier(n_estimators=100, random_state=42),
                "Gradient Boosting": GradientBoostingClassifier(n_estimators=100, learning_rate=0.1, random_state=42),
                "Logistic Regression": LogisticRegression(max_iter=500, random_state=42),
                "SVM (Support Vector Machine)": SVC(kernel='rbf', random_state=42),
                "KNN (K-Nearest Neighbors)": KNeighborsClassifier(n_neighbors=5),
                "Naive Bayes": GaussianNB(),
                "XGBoost": XGBClassifier(n_estimators=100, learning_rate=0.1, max_depth=5, random_state=42),
                "Decision Tree": DecisionTreeClassifier(random_state=42)
            }



            for name, clf in classifiers.items():
                print(f"=== {name} ===")

                # Trenowanie modelu
                clf.fit(X_train_smote, y_train_smote)

                # Predykcje
                y_pred = clf.predict(X_test_scaled)

                print("Accuracy:", accuracy_score(y_test, y_pred))
                print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred))
                print("Classification Report:\n", classification_report(y_test, y_pred))
                print("\n" + "=" * 50 + "\n")



                print(f"Complted for {name}")

            # break

except Exception as e:
    print(f"Error: {e}")

# finally:
#     writer.close()