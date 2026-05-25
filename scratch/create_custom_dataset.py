import csv
import os

input_file = 'd:/Terminator/train.csv'
output_file = 'd:/Terminator/custom_train_risks.csv'

def determine_highest_risk(row, header):
    try:
        # Extract fields, handling missing/dirty data safely
        debt_str = row[header.index('Outstanding_Debt')].replace('_', '')
        debt = float(debt_str) if debt_str else 0.0
        
        income_str = row[header.index('Annual_Income')].replace('_', '')
        income = float(income_str) if income_str else 1.0 # avoid div zero
        
        delayed_payments_str = row[header.index('Num_of_Delayed_Payment')].replace('_', '')
        delayed_payments = float(delayed_payments_str) if delayed_payments_str else 0.0
        
        delay_days_str = row[header.index('Delay_from_due_date')].replace('_', '')
        delay_days = float(delay_days_str) if delay_days_str else 0.0

        min_payment = row[header.index('Payment_of_Min_Amount')].strip()
        credit_score = row[header.index('Credit_Score')].strip()

        # Simple heuristic rules to define the "highest risk"
        debt_to_income = debt / income if income > 0 else 0
        
        # Rule 1: Financial Risk (High debt burden)
        if debt > 3000 or debt_to_income > 0.4:
            return "Financial Risk"
            
        # Rule 2: Behavioral Risk (Late payments, min payments)
        if delayed_payments > 10 or delay_days > 15 or min_payment == 'Yes':
            return "Behavioral Risk"
            
        # Rule 3: Credit Risk based on existing score if poor
        if credit_score == 'Poor':
            return "General Credit Risk"
            
        return "Low Risk"
    except Exception as e:
        # Fallback for parsing errors due to dirty data (e.g. strings in numeric cols)
        return "Unknown Risk"

def main():
    print(f"Reading from {input_file} and writing to {output_file}...")
    with open(input_file, mode='r', encoding='utf-8') as infile, \
         open(output_file, mode='w', encoding='utf-8', newline='') as outfile:
        
        reader = csv.reader(infile)
        writer = csv.writer(outfile)
        
        header = next(reader)
        # Add the new column
        new_header = header + ['Highest_Risk_Type']
        writer.writerow(new_header)
        
        count = 0
        for row in reader:
            if not row:
                continue
            # Determine risk
            risk = determine_highest_risk(row, header)
            writer.writerow(row + [risk])
            count += 1
            if count % 10000 == 0:
                print(f"Processed {count} rows...")
                
    print(f"Finished! Processed {count} rows total. Saved to {output_file}.")

if __name__ == '__main__':
    main()
