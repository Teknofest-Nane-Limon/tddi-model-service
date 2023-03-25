import os
from pathlib import Path
from typing import List, Dict

import requests
import torch
from fastapi import APIRouter
from pydantic import BaseModel, validator
from simpletransformers.classification import ClassificationModel

MODEL_PATH = (
    Path(__file__).resolve().parent.parent / "static" / "models" / "dummy_model.bin"
)

model_router = APIRouter()


class Item(BaseModel):
    """
    Input model for preprocessor API.
    """

    text: str

    @validator("text")
    def text_not_empty(cls, v):
        """
        Validator to ensure that text is not empty or contain only whitespace.
        """
        if not v.strip():
            raise ValueError("Text cannot be empty or contain only whitespace")
        return v


class Items(BaseModel):
    """
    Input model for preprocessor API.
    """

    texts: List[str]

    @validator("texts")
    def text_not_empty(cls, v):
        """
        Validator to ensure that text is not empty or contain only whitespace.
        """
        if len(v) == 0:
            raise ValueError("Text cannot be empty or contain only whitespace")
        return v


@model_router.post("/single_prediction", response_model=Dict[str, int])
async def single_prediction(item: Item, turkish_char: bool) -> Dict[str, int]:
    """
    This endpoint takes an instance of the Item class and a boolean value for turkish_char parameter.
    It preprocesses the text input, encodes it with the BERT tokenizer, and feeds it to a pre-trained BERT model
    (dbmdz/bert-base-turkish-128k-uncased) to perform a text classification.

    If the prediction label is 1, the text is considered offensive, and the 'is_offensive' key in the output
    dictionary will be 0. Otherwise, the 'is_offensive' key will be 1.

    Parameters:
    -----------
    item : Item
        An instance of the Item class that contains a text input.
    turkish_char bool
        A boolean value indicating whether to replace non-Turkish characters with their Turkish counterparts.

    Returns:
    --------
    return : dictionary
        A dictionary containing the predicted label and an indicator for whether the text is offensive or not.

    NOTE:
        This function uses a pre-trained BERT model for Turkish language available at
        'https://huggingface.co/dbmdz/bert-base-turkish-128k-uncased'.
    """
    torch.device("cuda")
    use_cuda = torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["CUDA_LAUNCH_BLOCKING"] = "1"
    model = ClassificationModel(
        "bert",
        "dbmdz/bert-base-turkish-128k-uncased",
        num_labels=5,
        use_cuda=use_cuda,
        args={
            "reprocess_input_data": True,
            "overwrite_output_dir": True,
        },
    )
    state_dict = torch.load(MODEL_PATH, map_location=device)
    model.model.load_state_dict(state_dict)

    tokenizer = model.tokenizer

    text = item.text
    preprocess_url = "https://cryptic-oasis-68424.herokuapp.com/single_preprocess"
    preprocess_params = {"turkish_char": turkish_char}
    preprocess_response = requests.post(
        preprocess_url, json={"text": text}, params=preprocess_params
    )
    processed_text = preprocess_response.json()["result"]

    encoded_input = tokenizer.encode_plus(
        processed_text, padding="max_length", max_length=512, return_tensors="pt"
    )

    outputs = model.model(**encoded_input)
    _, predicted = torch.max(outputs.logits, 1)
    prediction = predicted.item()

    if prediction == 1:
        is_offensive = 0
    else:
        is_offensive = 1

    return {"prediction": prediction, "is_offensive": is_offensive}

@model_router.post("/bulk_prediction")
async def bulk_prediction():
    return {"message": "Hello, World!"}