"""
Entry point to the program

- Accept and parse user commands
- Generate Potential Guides
- Run through biophysical model and report results
"""
import argparse
import os
import numpy as np
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from optimal_guide_finder import guide_generator
from optimal_guide_finder import guide_strength_calculator
import logging

def init_parser():
    """
    Initializes a parser to get user arguments using argparse

    Returns:
        ArgumentParser -- parser ready to accept arguments
    """
    # Parser to get the files listed in the arguments
    parser = argparse.ArgumentParser(description="""This program helps you to find all possible guide RNAs that will
                                       target the gene. Then using the model created by Salis Lab,
                                       you can see the off target effects for the each possible guide.""",
                                     formatter_class=argparse.RawTextHelpFormatter)

    # Parsers to add arguements.
    parser.add_argument("-t", "--target_sequence", required=True,
                        help="The Gene Sequence of Interest (Fasta or Genebank)")
    parser.add_argument("-g", "--genome_sequence", required=True, nargs='+',
                        help="""The Genome of the organism, if targeting a plasmid, make sure to \n
                              include it as well (Fasta or Genebank)""")
    parser.add_argument("-a", "--azimuth_cutoff", type=int, required=False,
                        default=10, help="""How many guides should pass from azimuth screening,
                              the guides are passed based on descending azimuth prediction score""")
    parser.add_argument("-o", "--output_path", required=False, default="output",
                        help="The path of the output folder generated by the program")
    parser.add_argument("-p", "--purpose", required=False, default="d",
                        help="""i: CRISPR interference on gene
                             # g: guide binding strength calculator
                             # Leave blank to see all possible guides and off target effects from your sequence""")
    parser.add_argument("-threads", required=False, default=None, type=int,
                        help="""Number of threads to use when running the program""")
    parser.add_argument("-c", "--copy_number", required=False, default=1, nargs='+',
                        help="""Number of copies of target gene present""")

    return parser

def get_sequence(args):
    """
    Returns the upper case sequences as strings from the files given as arguments.
    Also combines the various genome sequences
    """
    # Reads the file using biopython and creates an object called target
    target_dict = SeqIO.to_dict(SeqIO.parse(
        args.target_sequence, "fasta"))

    for name in target_dict:
        target_dict[name] = target_dict[name].seq.upper()

    # Reads the Genome files using biopython and combines them into one genome object
    genome = SeqRecord(Seq(""))
    for i in range(len(args.genome_sequence)):
        genome_parts = SeqIO.parse(args.genome_sequence[i], "fasta")
        for part in genome_parts:
            if args.copy_number == 1:
                genome.seq = genome.seq + part.seq
            else:
                genome.seq = genome.seq + part.seq * int(args.copy_number[i])

    return target_dict, genome.seq.upper()

def initialize_logger(output_file):
    #creating a basic logger
    logging.basicConfig(level=logging.INFO,
                        filename=output_file + '/run.log',
                        filemode='w')
    console_logger = logging.StreamHandler()
    console_logger.setLevel(logging.INFO)
    logging.getLogger().addHandler(console_logger)

def main():
    """
    Main workflow
    """
    parser = init_parser()

    # Creating a variable to make the values easily accessible
    args = parser.parse_args()

    #Create the path of the created genome file
    genome_location = args.output_path + '/Run_Genome'
    try:
        os.makedirs(args.output_path)
    except FileExistsError:
        pass

    # Get the sequences in a Seq format from user fasta or genebank files
    target_dict, genome = get_sequence(args)

    ref_record = SeqRecord(genome,
                           id="refgenome",
                           name="reference",
                           description="a reference background")
    ref_record = ref_record + ref_record.reverse_complement()
    SeqIO.write(ref_record, genome_location, "fasta")

    # Select the guides based on the purpose and the azimuth model
    guide_list = guide_generator.select_guides(target_dict, args)
    #Initialize the logger
    initialize_logger(args.output_path)

    # Build and run the model
    results_df = guide_strength_calculator.initalize_model(guide_list,
                                                           genome_location,
                                                           num_threads=args.threads)
    #generate and append Rank array
    results_df.sort_values(by=['Gene/ORF Name', 'Entropy Score'], inplace=True)
    results_df.drop_duplicates(inplace=True)
    rank_array = []
    for gene in results_df['Gene/ORF Name'].unique():
        num_guides = len(results_df[results_df['Gene/ORF Name'] == gene]['Guide Sequence'])
        rank_array.extend(list(np.arange(1, num_guides+1)))
    results_df['Rank in Target Gene'] = rank_array

    results_df.to_csv(args.output_path + '/output.csv', index=False)

if __name__ == "__main__":
    main()
