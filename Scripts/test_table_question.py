from search import generate_answer

query = "What is the shipping weight based on the number of poles?"
result = generate_answer(query)
print(f"Answer: {result['answer']}")
print(f"Sources: {result['sources']}")