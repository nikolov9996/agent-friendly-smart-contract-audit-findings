---
id: 16960
severity: "High"
---

# Making a payment to the protocol with `_dontMint` parameter will result in lost fund for user.

## Description

```solidity
User will have their funds lost if they tries to pay the protocol with `_dontMint = False`. A payment made with this parameter set should increase the `creditsOf[]` balance of user.

In `_processPayment()`, `creditsOf[_data.beneficiary]` is updated at the end if there are leftover funds. However, If `metadata` is provided and `_dontMint == true`, it immediately returns. [JBTiered721Delegate.sol#L524-L590](https://github.com/jbx-protocol/juice-nft-rewards/blob/f9893b1497098241dd3a664956d8016ff0d0efd0/contracts/JBTiered721Delegate.sol#L524-L590)

function _processPayment(JBDidPayData calldata _data) internal override {
    // Keep a reference to the amount of credits the beneficiary already has.
    uint256 _credits = creditsOf[_data.beneficiary];
    ...
    if (
      _data.metadata.length > 36 &&
      bytes4(_data.metadata[32:36]) == type(IJB721Delegate).interfaceId
    ) {
      ...
      // Don't mint if not desired.
      if (_dontMint) return;
      ...
    }
    ...
    // If there are funds leftover, mint the best available with it.
    if (_leftoverAmount != 0) {
      _leftoverAmount = _mintBestAvailableTier(
        _leftoverAmount,
        _data.beneficiary,
        _expectMintFromExtraFunds
      );

      if (_leftoverAmount != 0) {
        // Make sure there are no leftover funds after minting if not expected.
        if (_dontOverspend) revert OVERSPENDING();

        // Increment the leftover amount.
        creditsOf[_data.beneficiary] = _leftoverAmount;
      } else if (_credits != 0) creditsOf[_data.beneficiary] = 0;
    } else if (_credits != 0) creditsOf[_data.beneficiary] = 0;
}
```

## Proof of Concept

I’ve wrote a coded POC to illustrate this. It uses the same Foundry environment used by the project. Simply copy this function to `E2E.t.sol` to verify.
```solidity
function testPaymentNotAddedToCreditsOf() public{
    address _user = address(bytes20(keccak256('user')));
    (
      JBDeployTiered721DelegateData memory NFTRewardDeployerData,
      JBLaunchProjectData memory launchProjectData
    ) = createData();

    uint256 projectId = deployer.launchProjectFor(
      _projectOwner,
      NFTRewardDeployerData,
      launchProjectData
    );

    // Get the dataSource
    IJBTiered721Delegate _delegate = IJBTiered721Delegate(
      _jbFundingCycleStore.currentOf(projectId).dataSource()
    );

    address NFTRewardDataSource = _jbFundingCycleStore.currentOf(projectId).dataSource();

    uint256 _creditBefore = IJBTiered721Delegate(NFTRewardDataSource).creditsOf(_user);

    // Project is initiated with 10 different tiers with contributionFee of 10,20,30,40, .... , 100

    // Make payment to mint 1 NFT
    uint256 _payAmount = 10;
    _jbETHPaymentTerminal.pay{value: _payAmount}(
      projectId,
      100,
      address(0),
      _user,
      0,
      false,
      'Take my money!',
      new bytes(0)
    );

    // Minted 1 NFT
    assertEq(IERC721(NFTRewardDataSource).balanceOf(_user), 1);

    // Now, we make the payment but supply _dontMint metadata
    bool _dontMint = true;
    uint16[] memory empty;
    _jbETHPaymentTerminal.pay{value: _payAmount}(
      projectId,
      100,
      address(0),
      _user,
      0,
      false,
      'Take my money!',
      //new bytes(0)
      abi.encode(
        bytes32(0),
        type(IJB721Delegate).interfaceId,
        _dontMint,
        false,
        false,
        empty
        )
    );

    // NFT not minted
    assertEq(IERC721(NFTRewardDataSource).balanceOf(_user), 1);

    // Check that credits of user is still the same as before even though we have made the payment
    assertEq(IJBTiered721Delegate(NFTRewardDataSource).creditsOf(_user),_creditBefore);
}
```

## Recommendation

Update the `creditsOf[]` in the `if(_dontMint)` check.
```solidity
- if(_dontMint) return;
+ if(_dontMint){ creditsOf[_data.beneficiary] += _value; }
```
mixed feels. `_dontMint` basically says “Save me gas at all costs.”. I see the argument for value leaking being bad though. will mull over.

paying small amounts (under the floor or with `dontMint`) only to save them to later mint is a bit of a nonsense -> it’s way cheaper to just not pay, save in an eoa then mint within the same tx.

I have the feeling the severity is based on seeing `_credit` as a saving account, while it’s rather something to collect leftovers.

Anyway, we changed it, but not sure of high sev on this one, happy to see others’ point of view.

@drgorillamd @mejango I have to say that I don’t see why someone would use the `dontMint` flag in the first place. Wasn’t the original intent to use this flag specifically to modify `_credit` without minting? In the meantime I’ll keep the High label for this one, the `dontMint` functionality being flawed and leading to a loss of funds.

@Picodes `nftReward` is just an extension plugged into a Jb project -> `dontMint` is to avoid forcing users of the project who don’t want a nft reward when contributing, i.e. “classic” use of a Jb project. The use case we had in mind was smaller payers, wanting to get the erc20 (or even just donating), without the gas burden of a nft reward (which might, on L1, sometimes be more than the contribution itself). Does that make sense?

Definitely, thanks for the clarification @drgorillamd.

The final decision for this issue was to keep the high severity because of the leak of value and the possibility that some users use the function thinking it will change `_credit`, despite the fact that it was not the original intent of the code.

We ended up adding credits even when `_dontMint` is true!!  
It was a last minute design decision, initially we marked the issue as “Disagree with severity” and we were planning on keeping the code unchanged since it didnt pose a risk and was working as designed.  
We ended up changing the design, but the wardens’ feedback was ultimately helpful!

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability lies in the payment processingroutine of the tiered NFT reward delegate, where a user‑controlled flag intended to skip NFT minting (`_dontMint`) unintentionally prevents the contract from updating the internal accounting record that tracks leftover contribution credits (`creditsOf`). When a contribution is made with metadata that signals the delegate interface and sets `_dontMint` to true, the function `_processPayment` executes an early `return` before the code that adds any remaining funds to the caller’s credit balance. Consequently, the contributed ether is accepted by the payment terminal and deducted from the sender, but the contract’s state does not reflect the deposit; the user’s `creditsOf` entry remains unchanged. This logic flaw arises because the early exit bypasses the final block that conditionally mints the best available tier and, if any funds remain, increments `creditsOf`. The issue can be exploited by simply sending a payment with the “don’t mint” flag set – the transaction succeeds, no NFT is minted (as intended), yet the sender receives no credit for the contribution, effectively losing the funds. The impact is loss of user value and a breach of the protocol’s accounting guarantees: the protocol appears to have received funds that are not attributable to any user, and affected contributors cannot later redeem those credits for NFTs or refunds. The bug manifests only when the metadata length exceeds 36 bytes, matches the delegate interface identifier, and `_dontMint` is true; under those conditions the early return path is taken. All contributors who use the `dontMint` option, typically small payers who wish to avoid the gas cost of immediate NFT minting, are at risk. The flaw was discovered during a manual audit of the delegate’s source code, where the early‑return logic was inspected and a unit test demonstrated that after a payment with `_dontMint` the recorded credit balance stayed the same. Because the transaction does not revert and there is no explicit error message, the loss can be subtle – the UI may show a successful contribution with no NFT, and the user’s balance appears unchanged, leading to confusion. To remediate, the contract should update `creditsOf[_data.beneficiary]` before returning when `_dontMint` is true, ensuring that the contributed amount is properly recorded as credit. More generally, the bug belongs to the class of accounting‑state‑inconsistency errors caused by early returns that skip essential state updates, violating the protocol’s financial logic that every contribution must either result in an NFT mint or be stored as credit for later use.
