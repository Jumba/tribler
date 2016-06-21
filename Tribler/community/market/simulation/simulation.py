import random
from random import randint
from Tkinter import Tk, Canvas, Frame, BOTH
import math
import time

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

    NODE_AMOUNT = 6
    TICK_AMOUNT = 10

    def __init__(self):
        """
        Starts the specified amount of simulation nodes and insert the specified amount of ticks randomly across the nodes.
        """

        self._nodes = []
        self._create_nodes(self.NODE_AMOUNT)
        self._connect_nodes()

    def flush_buffers(self):
        for node in self._nodes:
            node.flush_buffer()

    def print_buffers(self):
        for node in self._nodes:
            node.print_buffer()

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
                    node.add_neighbour(neighbour, neighbour.location)

    def _simulate_ticks(self):
        """
        Simulates the specified amount of ticks, the tick type and the market community node are randomly determined
        :param amount: The amount of ticks to simulate
        """
        for i in xrange(0, self.TICK_AMOUNT):
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

    def messages(self):
        messages = []
        for node in self._nodes:
            print "node size" + str(len(node._buffer))
            for (neighbour, message) in node._buffer:
                messages.append(message)
        return messages

class TradeSimulationNode(object):
    """Trade simulation node containing an interface for a market community node."""

    def __init__(self, number):
        """
        Starts a market community node like in the market community test
        """
        self.name = "node-" + str(number)

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
        self._connected_nodes = []
        self._decorate_message_counters(self._market_community)
        self._mock_dispersy_send_message(self._market_community)
        self._mock_payment_providers(self._market_community)

        # Message buffer
        self._buffer = []

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
        self._connected_nodes.append(neighbour)

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

    def flush_buffer(self):
        for (neighbour, message) in self._buffer:
            neighbour.receive_message(message)
        self._buffer = []

    def print_buffer(self):
        for (neighbour, message) in self._buffer:
            print self.name + " -> " + neighbour.name

    def _send_neighbour(self, location, message):
        self._buffer.append((self._neighbours[location], message))
        # print self.name + " -> " + self._neighbours[location].name

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


class SimulationVisualization(object):
    def __init__(self):
        self.root = Tk()
        self.canvas = Canvas(self.root, width=800, height=800, bg='#e9e9e9')
        self.canvas.pack()

        self._simulation = TradeSimulation()
        self._simulation._simulate_ticks()

        self.progress = 0.05
        self.animation()

        self.canvas.pack()
        self.root.after(2, self.animation)
        self.root.mainloop()

    def animation(self):
        self.progress += 0.01
        if (self.progress > 1):
            self.progress = 0
            self._simulation.flush_buffers()
            self._simulation.print_buffers()
        self.canvas.delete("all")
        time.sleep(0.025)

        self._draw_nodes(self._simulation._nodes)
        self._draw_connection(self._simulation._nodes)
        self._draw_messages(self._simulation._nodes)

        self.canvas.update()
        self.root.after(2, self.animation)

    MID_X = 400
    MID_Y = 400
    MID_RADIUS = 300
    NODE_RADIUS = 50
    LINE_WIDTH = 3
    LINE_COLOR = '#404040'

    def _draw_nodes(self, nodes):
        for (i, node) in enumerate(nodes):
            node.x = self.MID_X + math.sin((2 * i * math.pi) / len(nodes)) * self.MID_RADIUS
            node.y = self.MID_Y + math.cos((2 * i * math.pi) / len(nodes)) * self.MID_RADIUS
            r = self.NODE_RADIUS
            self.canvas.create_oval(node.x - r, node.y - r, node.x + r, node.y + r, outline=self.LINE_COLOR, fill='#9dbffd',
                                    width=self.LINE_WIDTH)
            self.canvas.create_text(node.x, node.y, fill=self.LINE_COLOR, font=("Cambria", 18), text=node.name)

    def _draw_connection(self, nodes):
        for node in nodes:
            for neighbour in node._connected_nodes:
                line = self.canvas.create_line(node.x, node.y,
                                               neighbour.x, neighbour.y,
                                               fill=self.LINE_COLOR, width=self.LINE_WIDTH)
                self.canvas.tag_lower(line)

    def _draw_messages(self, nodes):

        for node in nodes:
            for (neighbour, message) in node._buffer:
                x = node.x + (neighbour.x - node.x) * self.progress
                y = node.y + (neighbour.y - node.y) * self.progress
                self._draw_message(message, x, y)

    MESSAGE_RADIUS = 8

    def _draw_message(self, message, x, y):
        r = self.MESSAGE_RADIUS
        self.canvas.create_oval(x - r, y - r, x + r, y + r, outline=self.LINE_COLOR, fill='green',
                                width=self.LINE_WIDTH)
        self.canvas.create_text(x, y - self.MESSAGE_RADIUS * 2, fill=self.LINE_COLOR, font=("Cambria", 12),
                                text=message._meta._name)  # Execute the trade visualization


visualization = SimulationVisualization()
statistics = visualization._simulation.statistics()
visualization._simulation._tear_down()

# Print the statistics dictionary
for key in statistics:
    if isinstance(statistics[key], dict):
        print key
        for nested_key in statistics[key]:
            print "\t" + nested_key + ": " + str(statistics[key][nested_key])
    else:
        print key + ": " + statistics[key]
