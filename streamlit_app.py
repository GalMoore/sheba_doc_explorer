import openai
import streamlit as st
import PyPDF2
import pandas as pd
from io import BytesIO
import json
import time

# Set the title of the Streamlit application
st.title("Sheba Documents Analyzer")

# Add a file uploader to the sidebar for the user to upload up to 10 documents
uploaded_files = st.sidebar.file_uploader("Upload up to 10 documents", accept_multiple_files=True, type=['pdf'])

# Initialize an empty list to store the extracted text from the uploaded files
data = []
filenames = []

# Loop over each uploaded file
if uploaded_files:
    st.sidebar.write("You have uploaded the following files:")
    for file in uploaded_files:
        st.sidebar.write(file.name)
        # Open the file as a stream
        file_stream = BytesIO(file.read())
        # Create a PDF file reader object
        pdf_reader = PyPDF2.PdfFileReader(file_stream)
        text = ""
        # Loop over each page in the PDF and extract the text
        for page in range(pdf_reader.getNumPages()):
            text += pdf_reader.getPage(page).extract_text()
        # Append the text to the data list
        data.append(text)
        # Append the filename to the filenames list
        filenames.append(file.name)

# Create a DataFrame
df = pd.DataFrame(data, columns=['Text'], index=filenames)

# Convert text to lowercase
df['Text'] = df['Text'].str.lower()

st.write(df)  # display the dataframe on the screen

# Set the OpenAI API key from Streamlit secrets
openai.api_key = st.secrets["openai_password"]

# Initialize the session state for the OpenAI model if it doesn't exist, with a default value of "gpt-4"
if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-4"

# Initialize the session state for the messages if it doesn't exist, as an empty list
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display all the existing messages in the chat, with the appropriate role (user or assistant)
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Wait for the user to input a message
if prompt := st.chat_input("What is up?"):
    # If the user inputs a message, append it to the session's messages with the role "user"
    st.session_state.messages.append({"role": "user", "content": prompt})
    # Display the user's message
    with st.chat_message("user"):
        st.markdown(prompt)

    # Prepare for the assistant's message
    with st.chat_message("assistant"):
        # Create a placeholder for the assistant's message
        message_placeholder = st.empty()
        # Initialize an empty string to build up the assistant's response
        full_response = ""
        # Generate the assistant's response using OpenAI's chat model, with the current session's messages as context
        # The response is streamed, which means it arrives in parts that are appended to the full_response string
        for response in openai.ChatCompletion.create(
            model=st.session_state["openai_model"],
            messages=[
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
            ],
            stream=True,
        ):
            # Append the content of the new part of the response to the full_response string
            full_response += response.choices[0].delta.get("content", "")
            # Update the assistant's message placeholder with the current full_response string, appending a "▌" to indicate it's still typing
            message_placeholder.markdown(full_response + "▌")
        # Once the full response has been received, update the assistant's message placeholder without the "▌"
        message_placeholder.markdown(full_response)
    # Append the assistant's full response to the session's messages with the role "assistant"
    st.session_state.messages.append({"role": "assistant", "content": full_response})

# Check if df["Text"][0] exists before calling example_document
if len(df) > 0 and "Text" in df.columns and len(df["Text"]) > 0:
    example_document = df["Text"][0]
    # Split the document into lines
    lines = example_document.split('\n')

    # # Print each line
    # for line in lines:
    #     print(line)
    #     st.write(line)
else:
    st.write("No document found.")


example_dict_outcome = {
    "ph": 7.458,
    "pco2": 40.9,
    "po2": 56.0,
    "hco3 (bicarbonate)-calc.": 28.3,
    "base excess": 4.1,
    "hematocrit": 29,
    "hemoglobin": 10.0,
    "saturation, o2": 88.4,
    "oxyhemoglobin": 88.0,
    "carboxyhemoglobin": 0.2,
    "methemoglobin": 0.3,
    "deoxyhemoglobin": 11.5,
    "sodium": 140,
    "potassium": 3.9,
    "calcium, ionized": 0.39,
    "chloride": 98,
    "anion gap": 17.2,
    "glucose": 147,
    "lactate": 13,
}

# Initialize a new column 'Messages' with dtype object
df['Messages'] = pd.Series(dtype=object)


### ONE SHOT LEARNING 

# Iterate through the DataFrame
for index, row in df.iterrows():
    print("collecting text from document in df and sending query to chatgpt ", index)
    document_text = row['Text']

    # Ask ChatGPT for dict of results for each document
    chat_response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": f"You are an israeli nurse in ICU with 20 years experience. When I give you a text string that includes a lab report like this: {example_document}, return a dictionary with the lab results like this: {example_dict_outcome}"},
            {"role": "user", \
             "content": f"{document_text}"}
        ]
    )

    # Extract the content field
    messages = chat_response["choices"][0]["message"]["content"]
    # Replace single quotes with double quotes
    messages = messages.replace("'", '"')
    # Convert string representation of dictionary back to dictionary
    print("messages ",messages)
    print("index ", index)

    try:
        messages_dict = json.loads(messages)
    except json.JSONDecodeError as e:
        print(f"Unable to parse message into a dictionary: {e}")
        continue

    # Convert dictionary into a string and update the corresponding column in the DataFrame
    df.at[index, 'Messages'] = json.dumps(messages_dict)

    # # Update the corresponding column in the DataFrame
    # df.at[index, 'Messages'] = messages_dict


st.write(df)  # display the dataframe on the screen


## From the gpt response - extract the dict of values
def extract_values(message_str):
    # Load string into dictionary
    message_dict = json.loads(message_str)

    # Define columns to extract
    cols = {
        "ph",
        "pco2",
        "po2",
        "hco3 (bicarbonate)-calc.",
        "base excess",
        "hematocrit",
        "hemoglobin",
        "saturation, o2",
        "oxyhemoglobin",
        "carboxyhemoglobin",
        "methemoglobin",
        "deoxyhemoglobin",
        "sodium",
        "potassium",
        "calcium, ionized",
        "chloride",
        "anion gap",
        "glucose",
        "lactate",
    }

    result = {}
    for key, value in message_dict.items():
        if isinstance(value, dict):
            # If the value is another dictionary, recurse
            result.update(extract_values(json.dumps(value)))  # convert dictionary back to string
        elif key in cols:
            result[key] = value
    return result
    
df = df.join(df['Messages'].apply(extract_values).apply(pd.Series), rsuffix='_extracted')
# df = df.join(df['Messages'].apply(extract_values).apply(pd.Series))
st.write(df)


# extract date and add to df


# Define the maximum number of attempts
MAX_ATTEMPTS = 5
example_date = "14-03-2023 01:12"

# # Iterate through the DataFrame
# for index, row in df.iterrows():
#     print("collecting text from document in df and sending query to chatgpt ", index)
#     document_text = row['Text']

#     # Ask ChatGPT for dict of results for each document
#     chat_response = openai.ChatCompletion.create(
#         model="gpt-3.5-turbo",
#         messages=[
#             {"role": "system", "content": f"You are an israeli nurse in ICU with 20 years experience. When I give you a text string that includes a lab report like this: {example_document}, return a string with the date and time like this: {example_date}"},
#             {"role": "user", \
#              "content": f"{document_text}"}
#         ]
#     )

# Iterate through the DataFrame
for index, row in df.iterrows():
    print("collecting text from document in df and sending query to chatgpt ", index)
    document_text = row['Text']

    # Try to execute the API call with retries
    for attempt in range(MAX_ATTEMPTS):
        try:
            # Ask ChatGPT for dict of results for each document
            chat_response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": f"You are an israeli nurse in ICU with 20 years experience. When I give you a text string that includes a lab report like this: {example_document}, return a string with the date and time like this: {example_date}"},
                    {"role": "user", \
                    "content": f"{document_text}"}
                ]
            )
            break
        except openai.error.ServiceUnavailableError:
            if attempt < MAX_ATTEMPTS - 1:  # i.e. if it's not the last attempt
                print(f"ServiceUnavailableError, retrying in 5 seconds...")
                time.sleep(5)  # Wait for 5 seconds before next retry
                continue
            else:
                raise
                
    # Extract the content field
    messages = chat_response["choices"][0]["message"]["content"]
    # Replace single quotes with double quotes
    messages = messages.replace("'", '"')
    # Convert string representation of dictionary back to dictionary
    print("messages ",messages)
    print("index ", index)

    # try:
    #     messages_dict = json.loads(messages)
    # except json.JSONDecodeError as e:
    #     print(f"Unable to parse message into a dictionary: {e}")
    #     continue

    # Convert dictionary into a string and update the corresponding column in the DataFrame
    df.at[index, 'Date'] = json.dumps(messages)


import re
from datetime import datetime

# The regular expression pattern for a date in the "dd-mm-yyyy hh:mm" format
date_pattern = r"\d{2}-\d{2}-\d{4} \d{2}:\d{2}"

# Iterate over the DataFrame
for index, row in df.iterrows():
    # Extract the original date from the Date column
    original_date_str = row['Date']
    try:
        # Search for the date in the original string
        match = re.search(date_pattern, original_date_str)
        if match:
            # If a date is found, extract it
            date_str = match.group()
            
            # Convert the date string to a datetime object
            date = datetime.strptime(date_str, '%d-%m-%Y %H:%M')

            # Convert the datetime object back to a string
            clean_date_str = datetime.strftime(date, '%d-%m-%Y %H:%M')

            # Add the cleaned date to the Date_clean column
            df.at[index, 'Date_clean'] = clean_date_str
        else:
            # If no date is found, print a message
            print(f"No date found in string {original_date_str} at index {index}")
    except ValueError:
        # In case the date string does not match the expected format
        print(f"Could not parse date string {original_date_str} at index {index}")


st.write(df)



















