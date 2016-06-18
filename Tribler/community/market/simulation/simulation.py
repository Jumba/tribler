import random

from twisted.python.threadable import registerAsIOThread

from Tribler.community.market.community import MarketCommunity
from Tribler.community.market.conversion import MarketConversion
from Tribler.community.tunnel.Socks5.server import Socks5Server
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import ManualEnpoint
from Tribler.dispersy.member import DummyMember
from Tribler.dispersy.requestcache import RequestCache


class TradeSimulation(object):
    """Simulation class for tick and trade functionality experiment."""

    NODE_AMOUNT = 10
    TICK_AMOUNT = 1000

    def __init__(self):
        """
        Starts the specified amount of simulation nodes and insert the specified amount of ticks randomly across the nodes.
        """
        self._nodes = []
        self._create_nodes(self.NODE_AMOUNT)
        self._simulate_ticks(self.TICK_AMOUNT)

    def _create_nodes(self, amount):
        """
        Creates the specified amount of nodes
        :param amount: The amount of nodes to create
        """
        for i in xrange(1, amount + 1):
            self._create_node(i)

    def _create_node(self, id):
        """
        Creates a market community node
        :param id: The identifier for the market community node
        """
        self._nodes.append(TradeSimulationNode(id))

    def _simulate_ticks(self, amount):
        """
        Simulates the specified amount of ticks, the tick type and the market community node are randomly determined
        :param amount: The amount of ticks to simulate
        """
        for i in xrange(0, amount):
            if random.random() > 0.5:
                self._simulate_bid(random.choice(self._nodes))
            else:
                self._simulate_ask(random.choice(self._nodes))

    def _simulate_bid(self, node):
        """
        Simulates a bid with semi-random parameters
        :param node: The market community node to simulate the bid on
        """
        price = 1.0
        quantity = 1.0
        timeout = float("inf")
        node.simulate_bid(price, quantity, timeout)

    def _simulate_ask(self, node):
        """
        Simulates an ask with semi-random parameters
        :param node: The market community node to simulate the ask on
        """
        price = 1.0
        quantity = 1.0
        timeout = float("inf")
        node.simulate_ask(price, quantity, timeout)

    def statistics(self):
        """
        :return: Dictionary with simulation statistics
        """
        statistics = {}
        statistics["total"] = {}
        statistics["total"]["ask count"] = 0
        statistics["total"]["bid count"] = 0

        for (i, node) in enumerate(self._nodes):
            statistics["total"]["ask count"] += len(node._asks)
            statistics["total"]["bid count"] += len(node._bids)
            statistics["node " + str(i + 1)] = {}
            statistics["node " + str(i + 1)][" ask count"] = len(node._asks)
            statistics["node " + str(i + 1)][" bid count"] = len(node._bids)
            statistics["node " + str(i + 1)] = node.message_counters

        return statistics


class TradeSimulationNode(object):
    """Trade simulation node containing an interface for a market community node."""

    def __init__(self, number):
        """
        Starts a market community node like in the market community test
        """
        # Faking IOThread
        registerAsIOThread()

        endpoint = ManualEnpoint(0)
        dispersy = Dispersy(endpoint, unicode("database/database_" + str(number)))
        dispersy._database.open()
        endpoint.open(dispersy)

        # Faking wan address vote
        ip = str(number) + '.' + str(number) + '.' + str(number) + '.' + str(number)
        dispersy.wan_address_vote((ip, number), Candidate((ip, number), False))

        # Object creation
        master_member = DummyMember(dispersy, 1, "a" * 20)
        member = dispersy.get_new_member(u"curve25519")
        self._market_community = MarketCommunity.init_community(dispersy, master_member, member)
        self._market_community._request_cache = RequestCache()
        self._market_community.socks_server = Socks5Server(self, 1234)
        self._market_community.add_conversion(MarketConversion(self._market_community))

        # Statistic initialization
        self._asks = []
        self._bids = []
        self._message_counters = {}
        self._decorate_message_counters(self._market_community)

    @property
    def message_counters(self):
        return self._message_counters

    def _message_counter_decorator(self, key, function):
        """
        :param key: The message counter key
        :param function: The function to be decorated with a message counter
        :return: The given function decorated with a message counter
        """

        def _message_counter(messages):
            function(messages)
            if key in self._message_counters:
                self._message_counters[key] += 1
            else:
                self._message_counters[key] = 1

        return _message_counter

    def _decorate_message_counters(self, market_community):
        """
        Decorates all on message functions with a message counter
        :param market_community: The market community to decorate
        """
        market_community.on_ask = self._message_counter_decorator("on ask count", market_community.on_ask)
        market_community.on_bid = self._message_counter_decorator("on bid count", market_community.on_bid)
        market_community.on_proposed_trade = self._message_counter_decorator("on proposed trade count",
                                                                             market_community.on_proposed_trade)
        market_community.on_declined_trade = self._message_counter_decorator("on declined trade count",
                                                                             market_community.on_declined_trade)
        market_community.on_proposed_trade = self._message_counter_decorator("on proposed trade count",
                                                                             market_community.on_proposed_trade)
        market_community.on_counter_trade = self._message_counter_decorator("on counter trade count",
                                                                            market_community.on_counter_trade)
        market_community.on_start_transaction = self._message_counter_decorator("on start transaction count",
                                                                                market_community.on_start_transaction)
        market_community.on_end_transaction = self._message_counter_decorator("on end transaction count",
                                                                              market_community.on_end_transaction)
        market_community.on_bitcoin_payment = self._message_counter_decorator("on bitcoin payment count",
                                                                              market_community.on_bitcoin_payment)
        market_community.on_multi_chain_payment = self._message_counter_decorator("on multi chain payment count",
                                                                                  market_community.on_multi_chain_payment)

    def simulate_ask(self, price, quantity, timeout):
        """
        Create an ask order (sell order)

        :param price: The price for the order in btc
        :param quantity: The quantity of the order in MB (10^6)
        :param timeout: The timeout of the order, when does the order need to be timed out
        :type price: float
        :type quantity: float
        :type timeout: float
        :return: The created order
        :rtype: Order
        """

        self._asks.append(self._market_community.create_ask(price, quantity, timeout))

    def simulate_bid(self, price, quantity, timeout):
        """
        Create a bid order (buy order)

        :param price: The price for the order in btc
        :param quantity: The quantity of the order in MB (10^6)
        :param timeout: The timeout of the order, when does the order need to be timed out
        :type price: float
        :type quantity: float
        :type timeout: float
        :return: The created order
        :rtype: Order
        """

        self._bids.append(self._market_community.create_bid(price, quantity, timeout))


# Execute the trade simulation
trade_simulation = TradeSimulation()
statistics = trade_simulation.statistics()

# Print the statistics dictionary
for key in statistics:
    print key
    if isinstance(statistics[key], dict):
        for nested_key in statistics[key]:
            print "\t" + nested_key
            print "\t\t" + str(statistics[key][nested_key])
    else:
        print "\t" + statistics[key]
