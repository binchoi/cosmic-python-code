import domain_model
from datetime import date, timedelta

today = date.today()
tomorrow = today + timedelta(days=1)
later = tomorrow + timedelta(days=10)

Order = lambda d: domain_model.Order(lines=[domain_model.OrderLine(sku, qty) for sku, qty in d.items()])
Stock = lambda d: domain_model.Stock(lines=[domain_model.OrderLine(sku, qty) for sku, qty in d.items()])
Shipment = lambda d, eta: domain_model.Shipment(
    lines=[domain_model.OrderLine(sku, qty) for sku, qty in d.items()],
    eta=eta,
)


def test_can_allocate_to_stock():
    order = Order({'a-sku': 10})
    stock = Stock({'a-sku': 1000})

    order.allocate(stock, shipments=[])

    assert order.allocation.sources['a-sku'] == stock
    assert stock.quantities['a-sku'] == 990


def test_can_allocate_to_shipment():
    order = Order({'a-sku': 10})
    shipment = Shipment({'a-sku': 1000}, eta=tomorrow)

    order.allocate(stock=Stock({}), shipments=[shipment])

    assert order.allocation.sources['a-sku'] == shipment
    assert shipment.quantities['a-sku'] == 990


def test_ignores_irrelevant_stock():
    order = Order({'sku1': 10})
    stock = Stock({'sku2': 1000})
    shipment = Shipment({'sku1': 1000}, eta=tomorrow)

    order.allocate(stock=stock, shipments=[shipment])

    assert order.allocation.sources['sku1'] == shipment



def test_can_allocate_to_correct_shipment():
    order = Order({'sku2': 10})
    shipment1 = Shipment({'sku1': 1000}, eta=tomorrow)
    shipment2 = Shipment({'sku2': 1000}, eta=tomorrow)

    order.allocate(stock=Stock({}), shipments=[shipment1, shipment2])

    assert order.allocation.sources['sku2'] == shipment2


def test_allocates_to_stock_in_preference_to_shipment():
    order = Order({'sku1': 10})
    stock = Stock({'sku1': 1000})
    shipment = Shipment({'sku1': 1000}, eta=tomorrow)

    order.allocate(stock, shipments=[shipment])

    assert order.allocation.sources['sku1'] == stock
    assert stock.quantities['sku1'] == 990
    assert shipment.quantities['sku1'] == 1000


def test_can_allocate_multiple_lines_to_wh():
    order = Order({'sku1': 5, 'sku2': 10})
    stock = Stock({'sku1': 1000, 'sku2': 1000})

    order.allocate(stock, shipments=[])
    assert order.allocation.sources['sku1'] == stock
    assert order.allocation.sources['sku2'] == stock
    assert stock.quantities['sku1'] == 995
    assert stock.quantities['sku2'] == 990


def test_can_allocate_multiple_lines_to_shipment():
    order = Order({'sku1': 5, 'sku2': 10})
    shipment = Shipment({'sku1': 1000, 'sku2': 1000}, eta=tomorrow)

    order.allocate(stock=Stock({}), shipments=[shipment])

    assert order.allocation.sources['sku1'] == shipment
    assert order.allocation.sources['sku2'] == shipment
    assert shipment.quantities['sku1'] == 995
    assert shipment.quantities['sku2'] == 990


def test_can_allocate_to_both():
    order = Order({'sku1': 5, 'sku2': 10})
    shipment = Shipment({'sku2': 1000}, eta=tomorrow)
    stock = Stock({'sku1': 1000})

    order.allocate(stock, shipments=[shipment])

    assert order.allocation.sources['sku1'] == stock
    assert order.allocation.sources['sku2'] == shipment
    assert stock.quantities['sku1'] == 995
    assert shipment.quantities['sku2'] == 990


def test_can_allocate_to_both_preferring_stock():
    order = Order({'sku1': 1, 'sku2': 2, 'sku3': 3, 'sku4': 4})
    shipment = Shipment({'sku1': 1000, 'sku2': 1000, 'sku3': 1000}, eta=tomorrow)
    stock = Stock({'sku3': 1000, 'sku4': 1000})

    order.allocate(stock, shipments=[shipment])

    assert order.allocation.sources['sku1'] == shipment
    assert order.allocation.sources['sku2'] == shipment
    assert order.allocation.sources['sku3'] == stock
    assert order.allocation.sources['sku4'] == stock
    assert shipment.quantities['sku1'] == 999
    assert shipment.quantities['sku2'] == 998
    assert shipment.quantities['sku3'] == 1000
    assert stock.quantities['sku3'] == 997
    assert stock.quantities['sku4'] == 996


def test_allocated_to_earliest_suitable_shipment_in_list():
    order = Order({'sku1': 10, 'sku2': 10})
    shipment1 = Shipment({'sku1': 1000, 'sku2': 1000}, eta=today)
    shipment2 = Shipment({'sku1': 1000, 'sku2': 1000}, eta=tomorrow)
    stock = Stock({})

    order.allocate(stock, shipments=[shipment2, shipment1])

    assert order.allocation.sources['sku1'] == shipment1
    assert order.allocation.sources['sku2'] == shipment1


def test_still_chooses_earliest_if_split_across_shipments():
    order = Order({'sku1': 10, 'sku2': 10, 'sku3': 10})
    shipment1 = Shipment({'sku1': 1000}, eta=today)
    shipment2 = Shipment({'sku2': 1000, 'sku3': 1000}, eta=tomorrow)
    shipment3 = Shipment({'sku2': 1000, 'sku3': 1000}, eta=later)
    stock = Stock({})

    order.allocate(stock, shipments=[shipment3, shipment2, shipment1])

    assert order.allocation.sources['sku1'] == shipment1
    assert order.allocation.sources['sku2'] == shipment2
    assert order.allocation.sources['sku3'] == shipment2


def test_stock_not_quite_enough_means_we_use_shipment():
    order = Order({'sku1': 10, 'sku2': 10})
    stock = Stock({'sku1': 10, 'sku2': 5})
    shipment = Shipment({
        'sku1': 1000,
        'sku2': 1000,
    }, eta=tomorrow)

    order.allocate(stock, shipments=[shipment])

    assert order.allocation.sources['sku1'] == shipment
    assert order.allocation.sources['sku2'] == shipment


def test_cannot_allocate_if_insufficent_quantity_in_stock():
    order = Order({'a-sku': 10})
    stock = Stock({'a-sku': 5})

    order.allocate(stock, shipments=[])

    assert 'a-sku' not in order.allocation.skus


def test_cannot_allocate_if_insufficent_quantity_in_shipment():
    order = Order({'a-sku': 10})
    shipment = Shipment({'a-sku': 5}, eta=tomorrow)

    order.allocate(stock=Stock({}), shipments=[shipment])

    assert 'a-sku' not in order.allocation.skus

