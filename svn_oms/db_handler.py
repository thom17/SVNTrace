from neo4j_manager.neo4jHandler import Neo4jHandler
from oms.dataset.info_base import InfoBase
from typing import List, Union, Tuple
from py2neo import Graph, Node, Relationship
class DBHandler:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", database='neo4j', password="123456789"):
        self.neo4j = Neo4jHandler(uri=uri, user=user, password=password, database=database)

    def save_data(self, data_list: List[InfoBase], revision: Union[int, str]):
        # neo4j_name
        nodes = [self.neo4j.data2node(data) for data in data_list]
        ip_nodes: List[Tuple[dict, str]] = []
        for node in nodes:
            data = dict(node)
            data['revision'] = revision #리비전 추가

            label_name = list(node.labels)[0] #일단 복잡하니 Label 그대로 사용
            # label_name = 'Rv' + list(node.labels)[0] #일단 Rv 추가.



            ip_nodes.append((data, label_name))

        self.neo4j.save_data(ip_nodes)

        # def check_search_save_data(self = self, ip_nodes = ip_nodes):
        def check_search_save_data():
            err_num = 0
            search_nodes = self.neo4j.search_node_map(ip_nodes)
            for pair in search_nodes:
                dict_data = pair[0][0]
                src_name = dict_data["src_name"]
                search_list = pair[1]
                size = len(search_list)
                print(f'{src_name} serach = {size}')
                if len(search_list) == 0:
                    err_num+=1
            return err_num
        assert check_search_save_data() == 0


    def print_info(self):
        self.neo4j.print_info()

    def delete_all_nodes(self):
        self.neo4j.delete_all_nodes()

    def add_relationship(self, data_list: List[Tuple[InfoBase, InfoBase, str]], **properties):
        '''
        그냥 클래스명 변경없이 혹은 변경된 클래스 입력 가정
        '''

        self.neo4j.add_relationship(data_list=data_list, **properties)


    # def add_relationship(self, data_list: List[Tuple[InfoBase, InfoBase, str]], **properties):
    #     '''
    #     이건 그냥 Neo4j 측 사용말고 여기서 직접 구현이 맞을듯
    #     :param data_list:
    #     :param properties:
    #     :return:
    #     '''
    #     def convert_node_list(data_list: List[Tuple[InfoBase, InfoBase]]) -> List[Tuple[Node, Node]]:
    #         convert_nodes = []
    #         for idx, (data1, data2, rel_type) in enumerate(data_list):
    #             nodes = [self.neo4j.data2node(data) for data in [data1, data2]]
    #             match_nodes = []
    #             for node in nodes:
    #                 type_name = f'RV{node.labels}'
    #                 data_dict = dict(node)
    #
    #                 try:
    #                     matched_nodes = list(self.neo4j.graph.match(type_name, **data_dict))
    #                 except e:
    #                     print(e)
    #                 assert len(matched_nodes) == 1, f'식별 불가능({len(matched_nodes)})개 검색됨. {node}'
    #
    #                 match_nodes.append(matched_nodes)
    #
    #             search_map = self.search_node_map([data1, data2])
    #             node1_list = matched_nodes[0]
    #             assert len(node1_list) == 1, f'식별 불가능({len(node1_list)})개 검색됨.\ndata_list[{idx}[0]] {data1}'
    #
    #             node2_list =matched_nodes[1]
    #             assert len(node2_list) == 1, f'식별 불가능({len(node2_list)})개 검색됨.\ndata_list[{idx}[1]] {data2}'
    #
    #             convert_nodes.append((node1_list[0], node2_list[0], rel_type))
    #         return convert_nodes
    #
    #     if not isinstance(data_list, List):
    #         data_list = [data_list]
    #
    #     node_list = convert_node_list(data_list=data_list)
    #
    #     tx = self.graph.begin()
    #     try:
    #         for node1, node2, rel_type in node_list:
    #             relationship = Relationship(node1, rel_type, node2, **properties)
    #             tx.create(relationship)
    #         tx.commit()
    #     except Exception as e:
    #         tx.rollback()  # 예외 발생 시 롤백
    #         raise e






