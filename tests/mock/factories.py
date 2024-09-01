from pydantic_factories import ModelFactory

from jit_utils.models.findings.entities import Finding, Ticket


class FindingFactory(ModelFactory):
    __model__ = Finding


class TicketFactory(ModelFactory):
    __model__ = Ticket
