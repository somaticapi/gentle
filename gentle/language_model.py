import logging
import math
import os
import shutil
import subprocess
import sys
import tempfile

from paths import get_binary
from metasentence import MetaSentence

MKGRAPH_PATH = get_binary("ext/mkgraph")

def make_bigram_lm_fst(word_sequences, conservative=False):
    '''
    Use the given token sequence to make a bigram language model
    in OpenFST plain text format.

    When the "conservative" flag is set, an [oov] is interleaved 
    between successive words.

    `Word sequence` is a list of lists, each valid as a start
    '''

    if len(word_sequences) == 0 or type(word_sequences[0]) != list:
        word_sequences = [word_sequences]

    bigrams = {'[oov]': set(['[oov]'])}

    for word_sequence in word_sequences:
        if len(word_sequence) == 0:
            continue
        
        prev_word = word_sequence[0]
        bigrams['[oov]'].add(prev_word) # valid start (?)
        
        for word in word_sequence[1:]:
            bigrams.setdefault(prev_word, set()).add(word)
            if conservative:
                bigrams[prev_word].add('[oov]')
            prev_word = word

        # ...valid end
        bigrams.setdefault(prev_word, set()).add('[oov]')

    node_ids = {}
    def get_node_id(word):
        node_id = node_ids.get(word, len(node_ids) + 1)
        node_ids[word] = node_id
        return node_id

    output = ""
    for from_word in sorted(bigrams.keys()):
        from_id = get_node_id(from_word)

        successors = bigrams[from_word]
        if len(successors) > 0:
            weight = -math.log(1.0 / len(successors))
        else:
            weight = 0

        for to_word in sorted(successors):
            to_id = get_node_id(to_word)
            output += '%d    %d    %s    %s    %f' % (from_id, to_id, to_word, to_word, weight)
            output += "\n"

    output += "%d    0\n" % (len(node_ids))

    return output

def make_bigram_language_model(kaldi_seq, proto_langdir='PROTO_LANGDIR', conservative=False):
    """Generates a language model to fit the text.

    Returns the filename of the generated language model FST.
    The caller is resposible for removing the generated file.

    `proto_langdir` is a path to a directory containing prototype model data
    `kaldi_seq` is a list of words within kaldi's vocabulary.
    """

    # Generate a textual FST
    txt_fst = make_bigram_lm_fst(kaldi_seq, conservative=conservative)
    txt_fst_file = tempfile.NamedTemporaryFile(delete=False)
    txt_fst_file.write(txt_fst)
    txt_fst_file.close()
    
    hclg_filename = tempfile.mktemp(suffix='_HCLG.fst')
    try:
        devnull = open(os.devnull, 'wb')
        subprocess.check_output([MKGRAPH_PATH,
                        proto_langdir,
                        txt_fst_file.name,
                        hclg_filename],
                        stderr=devnull)
    except Exception, e:
        try:
            os.unlink(hclg_filename)
        except:
            pass
        raise e
    finally:
        os.unlink(txt_fst_file.name)

    return hclg_filename

if __name__=='__main__':
    import sys
    make_bigram_language_model(open(sys.argv[1]).read())
