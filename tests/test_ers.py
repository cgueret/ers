import os
import couchdbkit

# Prefer ../ers-local/ers/ers.py over installed versions
# TODO: Use setuptools for testing without installing
import sys
TESTS_PATH = os.path.dirname(os.path.realpath(__file__))
ERS_PATH = os.path.join(os.path.dirname(TESTS_PATH), 'ers-local')
sys.path.insert(0, ERS_PATH)
from ers import ERSLocal, ModelS, ModelT

DEFAULT_MODEL = ModelS()
nt_file = os.path.join(TESTS_PATH, 'data', 'timbl.nt')

def test():
    server = couchdbkit.Server(r'http://admin:admin@127.0.0.1:5984/')

    def create_ers(dbname, model=DEFAULT_MODEL):
        if dbname in server:
            server.delete_db(dbname)           
        ers_new = ERSLocal(dbname=dbname, model=model)
        return ers_new
 
    def test_ers():
        """Model independent tests"""
        ers.import_nt(nt_file, 'timbl')
        assert ers.db.doc_exist('_design/index')
        assert ers.exist('http://www4.wiwiss.fu-berlin.de/booksMeshup/books/006251587X', 'bad_graph') == False
        assert ers.exist('http://www4.wiwiss.fu-berlin.de/booksMeshup/books/006251587X', 'timbl') == True
        ers.delete_entity('http://www4.wiwiss.fu-berlin.de/booksMeshup/books/006251587X', 'timbl')
        assert ers.exist('http://www4.wiwiss.fu-berlin.de/booksMeshup/books/006251587X', 'timbl') == False
        for o in objects:
            ers.add_data(s, p, o, g)
            ers.add_data(s, p2, o, g)
        for o in objects2:
            ers.add_data(s, p, o, g2)
            ers.add_data(s, p2, o, g2)
        data = ers.get_data(s, g)
        assert set(data[p]) == objects
        data2 = ers.get_data(s) # get data from all graphs
        assert set(data2[p]) == local_objects
        ers.delete_value(entity, p2)
        assert p2 not in ers.get_annotation(entity)


    # Test data
    s = entity = 'urn:ers:meta:testEntity'
    p = 'urn:ers:meta:predicates:hasValue'
    p2 = 'urn:ers:meta:predicates:property'
    g = 'urn:ers:meta:testGraph'
    g2 = 'urn:ers:meta:testGraph2'
    g3 = 'urn:ers:meta:testGraph3'
    objects = set(['value 1', 'value 2'])
    objects2 = set(['value 3', 'value 4'])
    local_objects = objects | objects2
    remote_objects = set(['value 5', 'value 6'])
    all_objects = local_objects | remote_objects

    # Test local ers using differend document models
    for model in [ModelS(), ModelT()]:
        dbname = 'ers_' + model.__class__.__name__.lower()
        ers = create_ers(dbname, model)
        test_ers()

    # Prepare remote ers
    ers_remote = create_ers('ers_remote')
    for o in remote_objects:
        ers_remote.add_data(entity, p, o, g3)

    # Query remote
    ers_local = ERSLocal(dbname='ers_models', fixed_peers=[{'url': r'http://admin:admin@127.0.0.1:5984/',
                                                            'dbname': 'ers_remote'}])
    assert set(ers_local.get_annotation(entity)[p]) == all_objects
    assert set(ers_local.get_values(entity, p)) == all_objects
    assert set(ers_local.search(p)) == set((s, graph) for graph in (g, g2, g3))
    ers_local.delete_entity(entity)
    assert set(ers_local.get_annotation(entity)[p]) == remote_objects

    print "Tests pass"


if __name__ == '__main__':
    test()
