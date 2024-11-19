import csv


def fill_na_with_data(main_file, helper_file, output_file):


    helper_data = {}
    with open(helper_file, mode='r', encoding='utf-8') as hfile:
        reader = csv.reader(hfile)
        helper_header = next(reader)

        for row in reader:
            club = row[0]
            year_data = dict(zip(helper_header[1:], row[1:]))
            helper_data[club] = year_data

    # Process the main file
    with open(main_file, mode='r', encoding='utf-8') as mfile:
        reader = csv.reader(mfile)
        main_header = next(reader)

        updated_data = [main_header]
        for row in reader:
            club = row[0]
            updated_row = row[:]


            if club in helper_data:
                for i, value in enumerate(row[1:], start=1):
                    if value.strip().upper() == 'N/A':
                        year = main_header[i]
                        updated_row[i] = helper_data[club].get(year, 'N/A')

            updated_data.append(updated_row)


    with open(output_file, mode='w', encoding='utf-8', newline='') as ofile:
        writer = csv.writer(ofile)
        writer.writerows(updated_data)



fill_na_with_data('../Data/Club Info/clubs_report_from_transfermarkt.csv', '../Data/Club Info/filtred_clubs_report_from_transfermarkt.csv', '../Data/Club Info/all_clubs_report_from_transfermarkt.csv')
