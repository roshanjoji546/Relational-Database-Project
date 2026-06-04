# Relational-Database-Project

This project aimed to design and implement a relational database system for a retail business, converting transaction, customer, and credit card data from three separate CSV files into a structured SQLite database.

The original data was stored in three CSV files containing customer details, transaction records, product information, and credit card details. A relational database in the Third Normal Form was designed to minimise data redundancy and maintain data integrity.

An Entity Relationship Diagram was produced using crow's foot notation and implemented in SQLite. The database consisted of five entities:
* Customer
* Transactions
* Product
* Transaction_Item
* Credit_Card

Primary keys, foreign keys, and referential integrity contraints were implemented in the SQL schema. A junction table (Transaction _Item) was used to resolve many-to-many relationships between transactions and products.

A python script was developed to created and populate the SQLite database. The script used:
* SQLite3 for database creation and management
* Pandas for data loading and manipulation
* Regular expressions (regex) for data cleaning and validation

Extensive data cleaning was performed prior to database population including:
* Removing rows with missing key identifiers
* Converting dates to ISO format
* Standardising numeric data types
* Cleaning corrupted customer names
* Normalising credit card provider information
* Correcting credit card numbers stored in inconsistent formats
* Removing invalid or incomplete records

Customer information from multiple datasets was merged to create a unified customer master table. Credit card records were matched to customers using cleaned customer names, as customer identifiers were not available within the credit card dataset.

Python scripts were written to:
* Create the database schema using SQL CREATE TABLE statements
* Read and clean data from multiple CSV files
* Transform and standardise data values
* Populate all database tables
* Validate successful database creation and population through verification checks

### Skills Demonstrated
* Relational database design
* Database normalisation (3NF)
* SQL schema development
* SQLite
* Python programming
* Pandas
* Data cleaning and processing
