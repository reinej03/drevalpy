from typing import Optional
from models_code.SimpleNeuralNetwork.utils import FeedForwardNetwork
from suite.model_wrapper import DRPModel
from suite.data_wrapper import DrugResponseDataset, FeatureDataset
import numpy as np
import pandas as pd
class SimpleNeuralNetwork(DRPModel):
    """
    Wrapper class to be implemented for a new custom model.
    """

    cell_line_views = ["gene_expression"]

    drug_views = ["fingerprints"]

    def build_model(self, *args, **kwargs):
        """
        Builds the model.
        """
        pass
    def get_feature_matrix(self, drug_input: FeatureDataset, cell_line_input: FeatureDataset, output: DrugResponseDataset):
        X_drug = drug_input.get_feature_matrix("fingerprints", output.drug_ids)
        X_cell_line = cell_line_input.get_feature_matrix("gene_expression", output.cell_line_ids)
        X = np.concatenate((X_drug, X_cell_line), axis=1)
        return X
    def train(self, cell_line_input: FeatureDataset,
                drug_input: FeatureDataset,
                output: DrugResponseDataset,
                hyperparameters: dict,
                cell_line_input_earlystopping: Optional[FeatureDataset] = None,
                drug_input_earlystopping: Optional[FeatureDataset] = None,
                output_earlystopping: Optional[DrugResponseDataset] = None):
        """
        Trains the model.
        :param cell_line_input: training data associated with the cell line input
        :param drug_input: training data associated with the drug input
        :param output: training data associated with the reponse output
        """
        X = self.get_feature_matrix(drug_input, cell_line_input, output)    
        
        if cell_line_input_earlystopping and drug_input_earlystopping and output_earlystopping:
            X_earlystopping = self.get_feature_matrix(drug_input_earlystopping,
                                                      cell_line_input_earlystopping,
                                                      output_earlystopping)   
        else:
            X_earlystopping = None
        
        neural_network = FeedForwardNetwork(n_features=X.shape[1], n_units_per_layer=hyperparameters["units_per_layer"],
                           dropout_prob=hyperparameters["dropout_prob"])
        if output_earlystopping:
            response_earlystopping = output_earlystopping.response
        else:
            response_earlystopping = None
        neural_network.fit(X, output.response, X_earlystopping,
                           response_earlystopping,
                           batch_size=64,
                           patience=5,
                           num_workers=2)
        self.model = neural_network
        

    def predict(self, cell_line_input: FeatureDataset, drug_input: FeatureDataset):
        """
        Predicts the response for the given input. Call the respective function from models_code here.
        :param cell_line_input: input associated with the cell line
        :param drug_input: input associated with the drug
        :return: predicted response
        """
        X = self.get_feature_matrix(drug_input, cell_line_input, None)
        return self.model.predict(X)


    def save(self, path):
        """
        Saves the model.
        :param path: path to save the model
        """
        pass

    def load(self, path):
        """
        Loads the model.
        :param path: path to load the model
        """
        pass

    def get_cell_line_features(self, path: str)-> FeatureDataset:
        """
        Fetch cell line input data 
        :return: FeatureDataset
        """
        ge = pd.read_csv(f"{path}/gene_expression.csv", index_col=0)
        landmark_genes = pd.read_csv(f"{path}/gene_lists/landmark_genes.csv", sep="\t")
        genes_to_use = set(landmark_genes["Symbol"]) & set(ge.columns)
        ge = ge[list(genes_to_use)]      
        
        return FeatureDataset({cl: {"gene_expression": ge.loc[cl].values} for cl in ge.index})
        
    def get_drug_features(self, path: str)-> FeatureDataset:
        """
        Fetch drug input data.
        :return: FeatureDataset
        """
        fingerprints = pd.read_csv(f"drug_fingerprints/drug_name_to_demorgan_128_map.csv", index_col=0).T
        return FeatureDataset({drug: {"fingerprints": fingerprints.loc[drug].values} for drug in fingerprints.index})
