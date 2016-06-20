import random
from random import randint

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

    NODE_AMOUNT = 2
    TICK_AMOUNT = 10

    def __init__(self):
        """
        Starts the specified amount of simulation nodes and insert the specified amount of ticks randomly across the nodes.
        """
        self._nodes = []
        self._create_nodes(self.NODE_AMOUNT)
        self._connect_nodes()
        self._simulate_ticks(self.TICK_AMOUNT)
        self._tear_down()

    def _tear_down(self):
        """
        Tear down market communities after simulation
        """
        for node in self._nodes:
            node.tear_down()

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

    def _connect_nodes(self):
        for node in self._nodes:
            for neighbour in self._nodes:
                if not node == neighbour:
                    node.add_neighbour(neighbour, neighbour.location, )

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
        price = randint(3, 10)
        quantity = randint(3, 10)
        timeout = float("inf")
        node.simulate_bid(price, quantity, timeout)

    def _simulate_ask(self, node):
        """
        Simulates an ask with semi-random parameters
        :param node: The market community node to simulate the ask on
        """
        price = randint(3, 10)
        quantity = randint(3, 10)
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
            statistics["node-" + str(i + 1)] = {}
            statistics["node-" + str(i + 1)]["ask count"] = len(node._asks)
            statistics["node-" + str(i + 1)]["bid count"] = len(node._bids)
            statistics["node-" + str(i + 1)] = node.message_counters

        return statistics


class TradeSimulationNode(object):
    """Trade simulation node containing an interface for a market community node."""

    def __init__(self, number):
        """
        Starts a market community node like in the market community test
        """
        # Faking IOThread
        registerAsIOThread()

        self._endpoint = ManualEnpoint(0)
        self._dispersy = Dispersy(self._endpoint, unicode("database/database_" + str(number)))
        self._dispersy._database.open()
        self._endpoint.open(self._dispersy)

        # Faking wan address vote
        ip = str(number) + '.' + str(number) + '.' + str(number) + '.' + str(number)
        self._dispersy.wan_address_vote((ip, number), Candidate((ip, number), False))
        self._location = (ip, number)

        # Object creation
        master_member = DummyMember(self._dispersy, 1, "a" * 20)
        member = self._dispersy.get_new_member(u"curve25519")
        self._market_community = MarketCommunity.init_community(self._dispersy, master_member, member)
        self._market_community._request_cache = RequestCache()
        self._market_community.socks_server = Socks5Server(self, 1234)
        self._market_community.add_conversion(MarketConversion(self._market_community))

        # Statistic initialization
        self._asks = []
        self._bids = []
        self._message_counters = {}

        self._neighbours = {}
        self._decorate_message_counters(self._market_community)
        self._mock_dispersy_send_message(self._market_community)
        self._mock_payment_providers(self._market_community)

    @property
    def location(self):
        """
        :return: The location (ip, port) of this market community node
        """
        return self._location

    @property
    def message_counters(self):
        """
        :return: List of message counter statistics
        """
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
        market_community.on_ask = self._message_counter_decorator("received ask count", market_community.on_ask)
        market_community.on_bid = self._message_counter_decorator("received bid count", market_community.on_bid)
        market_community.on_proposed_trade = self._message_counter_decorator("received proposed trade count",
                                                                             market_community.on_proposed_trade)
        market_community.on_declined_trade = self._message_counter_decorator("received declined trade count",
                                                                             market_community.on_declined_trade)
        market_community.on_proposed_trade = self._message_counter_decorator("received proposed trade count",
                                                                             market_community.on_proposed_trade)
        market_community.on_counter_trade = self._message_counter_decorator("received counter trade count",
                                                                            market_community.on_counter_trade)
        market_community.on_accepted_trade = self._message_counter_decorator("received accepted trade count",
                                                                            market_community.on_accepted_trade)
        market_community.on_start_transaction = self._message_counter_decorator("received start transaction count",
                                                                                market_community.on_start_transaction)
        market_community.on_end_transaction = self._message_counter_decorator("received end transaction count",
                                                                              market_community.on_end_transaction)
        market_community.on_bitcoin_payment = self._message_counter_decorator("received bitcoin payment count",
                                                                              market_community.on_bitcoin_payment)
        market_community.on_multi_chain_payment = self._message_counter_decorator("received multi chain payment count",
                                                                                  market_community.on_multi_chain_payment)

    def add_neighbour(self, neighbour, location):
        """
        :param neighbour: the market community
        :param location: (ip, port) of the market community node
        :return:
        """
        self._neighbours[location] = neighbour

    def receive_message(self, message):
        """
        Processes a received message from another market community node
        :param message: The message to be processed
        """
        if message._meta._name == u"ask":
            self._market_community.on_ask([message])
            return
        if message._meta._name == u"bid":
            self._market_community.on_bid([message])
            return
        if message._meta._name == u"proposed-trade":
            self._market_community.on_proposed_trade([message])
            return
        if message._meta._name == u"counter-trade":
            self._market_community.on_counter_trade([message])
            return
        if message._meta._name == u"accepted-trade":
            self._market_community.on_accepted_trade([message])
            return
        if message._meta._name == u"declined-trade":
            self._market_community.on_declined_trade([message])
            return
        if message._meta._name == u"start-transaction":
            self._market_community.on_start_transaction([message])
            return
        if message._meta._name == u"continue-transaction":
            self._market_community.on_continue_transaction([message])
            return
        if message._meta._name == u"end-transaction":
            self._market_community.on_end_transaction([message])
            return
        if message._meta._name == u"multi-chain-payment":
            self._market_community.on_multi_chain_payment([message])
            return
        if message._meta._name == u"bitcoin-payment":
            self._market_community.on_bitcoin_payment([message])
            return

    def _send_neighbour(self, location, message):
        self._neighbours[location].receive_message(message)

    def _send_neighbours(self, message):
        for location in self._neighbours:
            self._send_neighbour(location, message)

    def _mock_dispersy_send_message(self, market_community):
        """
        Mocks the send message function in dispersy with replaced functionality
        :param market_community: The market community to decorate
        """

        def send_message(messages, store, update, forward):
            for message in messages:
                if len(message._destination.candidates) > 0:
                    for candidate in message._destination.candidates:
                        self._send_neighbour(candidate._sock_addr, message)
                else:
                    self._send_neighbours(message)

        market_community.dispersy.store_update_forward = send_message

    def _mock_payment_providers(self, market_community):
        """
        Mocks the payment providers in the market community
        :param market_community: The market community to mock the payment providers from
        """

        market_community.multi_chain_payment_provider = SimulationMultiChainPaymentProvider()
        market_community.bitcoin_payment_provider = SimulationBitcoinPaymentProvider()

    def simulate_ask(self, price, quantity, timeout):
        """
        Create an ask order (sell order)

        :param price: The price for the order in btc
        :param quantity: The quantity of the order in MB (10^6)
        :param timeout: The timeout of the order, when does the order need to be timed out
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
        :return: The created order
        :rtype: Order
        """
        self._bids.append(self._market_community.create_bid(price, quantity, timeout))

    def tear_down(self):
        """
        Closing and unlocking dispersy database for other tests in test suite
        """
        self._dispersy._database.close()
        self._endpoint.close()


class SimulationMultiChainPaymentProvider(object):

    def transfer_multi_chain(self, candidate, quantity):
        return

    def balance(self):
        return


class SimulationBitcoinPaymentProvider(object):

    def transfer_bitcoin(self, bitcoin_address, price):
        return

    def balance(self):
        return


# Execute the trade simulation
trade_simulation = TradeSimulation()
statistics = trade_simulation.statistics()

# Print the statistics dictionary
for key in statistics:
    if isinstance(statistics[key], dict):
        print key
        for nested_key in statistics[key]:
            print "\t" + nested_key + ": " + str(statistics[key][nested_key])
    else:
        print key + ": " + statistics[key]
